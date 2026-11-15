"""Check step (T22): test what the model read from one hospital record against the record itself.

Section 5 of docs/Handover_Pipeline_and_Frontend_Plan.md: "Extracted facts and the
source record -> facts marked verified or flagged, one retry." No model calls here
(CLAUDE.md, Model calls): this file reads saved extractions only. The one retry is
made by the extract step, which asks this file whether a retry is needed.

What is checked, fact by fact:

  1. Shape.       The file matches shared/schema/extracted.schema.json.
  2. Status.      The status is allowed for the fact's type (shared/fixed_lists.json).
  3. Quote.       The quote appears word for word in the source record. Line breaks and
                  runs of spaces may differ; nothing else may.
  4. Name.        The name as written appears inside the quote (capitals ignored).
  5. Dose.        The dose's number appears in the quote ("1000 mg" may be written "1 g").
  6. Brand name.  Allergies and medicines get their generic name from
                  shared/brand_to_generic.csv and shared/drug_list.csv, capitals ignored,
                  longest brand first ("Glucophage XR" before "Glucophage"). A name in
                  neither table gets name = null and the `unknown_name` flag. Never guessed.
                  Diagnoses and operations have no tables: their name is the name as
                  written in the record, in lowercase, so every hospital names it the same.

A fact that fails 3, 4 or 5 is kept, with the `unverified` flag, so the doctor sees it
with a warning rather than losing it. Any failure of 1 to 5 makes the record "fail the
check", which earns the one retry. Unknown names do not earn a retry: the model can't
fix a name our table doesn't know.

Small tidying that is not a failure (each one is written to the report):
  * "1 g" becomes "1000 mg" (record format: convert g to mg).
  * Names are made lowercase; name becomes null for "none recorded" facts.
  * Dose and frequency are cleared on non-medicines, reaction on non-allergies.
  * A current medicine with no dose gets the `missing_dose` flag.

The one retry (CLAUDE.md: one retry only, only when an extraction fails the Check step):

  * check_with_retry(first, source_text, extract_again) is for the extract step (T19/T20).
    It checks the first try. Only if that fails does it call extract_again(problems)
    once; the extract step makes the second model call, saves it as
    <P>_<H>.attempt2.json, and returns it. Of the two tries, the one with fewer
    problems is kept (the retry wins a tie). There is never a third call.
  * The command line reads saved files only. If a first try failed and no attempt2 file
    exists yet, the record is listed under "needs_retry" so the extract step can make it.

Command line:

    python pipeline/tool/check.py --run <run_id>
    python pipeline/tool/check.py --run <run_id> --patients P001 P002

Reads outputs/extracted/<run_id>/P001_A.json (and P001_A.attempt2.json if present),
writes outputs/checked/<run_id>/P001_A.json and outputs/checked/<run_id>/check_report.json.
Held-out and reserve patients: only IDs and counts are printed, never contents
(CLAUDE.md, Held-out patients).
"""
import argparse
import copy
import csv
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

TOOL = Path(__file__).resolve().parent
REPO = TOOL.parent.parent
SHARED = REPO / "shared"
DATA = REPO / "pipeline" / "data"
OUTPUTS = REPO / "outputs"

DRUG_TYPES = {"allergy", "medicine"}


# ---------------------------------------------------------------- shared files

def _load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


_CACHE = {}


def shared_tables():
    """Load the schema, the allowed statuses, the brand table and the drug list once."""
    if not _CACHE:
        schema = _load_json(SHARED / "schema" / "extracted.schema.json")
        lists = _load_json(SHARED / "fixed_lists.json")
        brands, generics = {}, set()
        with open(SHARED / "brand_to_generic.csv", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                brands[row["brand"].strip().lower()] = row["generic"].strip().lower()
        with open(SHARED / "drug_list.csv", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                generics.add(row["name"].strip().lower())
        generics.update(brands.values())
        # Every known name, longest first, so "glucophage xr" is tried before "glucophage".
        # Keys are spelled the way name_key() spells a name, so lookups line up.
        known = {**{name_key(g): g for g in generics}, **{name_key(b): g for b, g in brands.items()}}
        longest_first = sorted(known, key=len, reverse=True)
        _CACHE.update(validator=Draft202012Validator(schema),
                      allowed=lists["statuses_allowed_by_type"],
                      known=known, longest_first=longest_first)
    return _CACHE


# ---------------------------------------------------------------- small helpers

def squash(text):
    """Collapse line breaks and runs of spaces into one space (for the quote check)."""
    return re.sub(r"\s+", " ", text).strip()


def lower_squash(text):
    return squash(text).lower() if text else ""


def name_key(text):
    """A name ready for table lookup: lowercase, single spaces, and combination
    medicines written the table's way. Hospital B writes "amoxicillin and clavulanate";
    the table says "amoxicillin / clavulanate"."""
    key = lower_squash(text)
    key = re.sub(r"\s*(?:/|\+|&|\band\b|\bwith\b)\s*", " / ", key)
    return squash(key)


def exact_generic(text):
    """The generic name if the whole text is a known name (capitals ignored), else None."""
    return shared_tables()["known"].get(name_key(text)) if text else None


def partial_generic(text):
    """The longest known name found inside the text as whole words, e.g.
    "Glucophage XR 500" -> metformin. None if no known name is inside it."""
    if not text:
        return None
    t = shared_tables()
    key = name_key(text)
    for name in t["longest_first"]:
        if re.search(r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])", key):
            return t["known"][name]
    return None


def to_generic(written, name):
    """Check 6: the generic name for a fact, or None if neither table knows it.

    Exact matches come first (the name as written, then the model's name), and only
    then partial matches, so "amoxicillin / clavulanate" is never cut down to
    "amoxicillin". The written name goes first because it is the one checked against
    the quote.
    """
    return (exact_generic(written) or exact_generic(name)
            or partial_generic(written) or partial_generic(name))


def tidy_dose(dose):
    """'1 g' -> '1000 mg', '0.5 g' -> '500 mg'. Other doses are returned unchanged."""
    if not dose:
        return dose
    m = re.fullmatch(r"(\d+(?:\.\d+)?) g", dose)
    if not m:
        return dose
    text = f"{float(m.group(1)) * 1000:.3f}".rstrip("0").rstrip(".")
    return f"{text} mg"


def number_in(number, text):
    """True if this number stands on its own in the text ("1" is in "1 g BD", not in "10 mg")."""
    return re.search(r"(?<![\d.])" + re.escape(number) + r"(?!\d|\.\d)", text) is not None


def dose_in_quote(dose, quote):
    """Rule 5: the dose's number is in the quote, either as mg or as grams."""
    number, unit = dose.split(" ", 1)
    if number_in(number, quote):
        return True
    if unit == "mg":  # the record may have written grams ("1 g" for "1000 mg")
        grams = f"{float(number) / 1000:.3f}".rstrip("0").rstrip(".")
        return number_in(grams, quote)
    return False


# ---------------------------------------------------------------- checking one record

def check_record(doc, source_text):
    """Check one extracted record against its source record text.

    Returns a dict:
      checked   the cleaned record (extracted shape), or None if the shape was wrong
      problems  list of plain-language reasons the record fails the check (empty = passed)
      notes     tidying that was done (not failures)
      unknown   number of facts with a name neither table knows
    """
    t = shared_tables()

    # Check 1: the shape. If it's wrong, the facts can't be trusted at all.
    shape_errors = [f"shape: {'/'.join(map(str, e.path)) or 'file'}: {e.message}"
                    for e in t["validator"].iter_errors(doc)]
    if shape_errors:
        return {"checked": None, "problems": shape_errors, "notes": [], "unknown": 0}

    out = copy.deepcopy(doc)
    problems, notes, unknown = [], [], 0
    source_squashed = squash(source_text)
    source_lower = source_squashed.lower()

    for i, f in enumerate(out["facts"]):
        label = f"fact {i + 1} ({f['type']} '{f.get('name_as_written') or f.get('name')}')"
        flags = set(f["flags"])
        verified = True

        # Check 2: status allowed for this type.
        if f["status"] not in t["allowed"][f["type"]]:
            problems.append(f"{label}: status '{f['status']}' is not allowed for {f['type']}")

        # Check 3: the quote is in the record, word for word.
        quote = f["quote"]
        if quote not in source_text and squash(quote) not in source_squashed:
            problems.append(f"{label}: quote not found in the record")
            verified = False

        # Check 4: the name as written is inside the quote.
        written = f.get("name_as_written")
        if written and lower_squash(written) not in lower_squash(quote):
            problems.append(f"{label}: name as written is not in the quote")
            verified = False

        # Tidying: fields that don't belong to this type are cleared.
        if f["type"] != "medicine" and (f["dose"] or f["frequency"]):
            f["dose"], f["frequency"] = None, None
            notes.append(f"{label}: cleared dose/frequency (not a medicine)")
        if f["type"] != "allergy" and f["reaction"]:
            f["reaction"] = None
            notes.append(f"{label}: cleared reaction (not an allergy)")

        # Check 5: the dose is in the quote. Grams become milligrams first.
        if f["dose"]:
            new = tidy_dose(f["dose"])
            if new != f["dose"]:
                notes.append(f"{label}: dose '{f['dose']}' written as '{new}'")
                f["dose"] = new
            if not dose_in_quote(f["dose"], quote):
                problems.append(f"{label}: dose '{f['dose']}' is not in the quote")
                verified = False

        # Check 6: generic name from the tables. "None recorded" facts have no name.
        if f["status"] == "none_recorded":
            if f["name"] is not None:
                notes.append(f"{label}: name cleared (none recorded)")
            f["name"] = None
        elif f["type"] in DRUG_TYPES:
            # The written name is the one we can check against the quote, so it goes first.
            generic = to_generic(written, f["name"])
            if generic is None:
                unknown += 1
                flags.add("unknown_name")
                if f["name"] is not None:
                    notes.append(f"{label}: '{f['name']}' is in neither table, name set to null")
                f["name"] = None
            else:
                if f["name"] and f["name"].lower() != generic:
                    notes.append(f"{label}: name '{f['name']}' changed to '{generic}' from the tables")
                f["name"] = generic
                flags.discard("unknown_name")
        else:
            # Diagnoses and operations have no tables, so the name is the record's own
            # words (already checked against the quote in check 4), in lowercase. The
            # model sometimes shortens a name ("asthma" for "Childhood asthma"), and then
            # the same illness from two hospitals would not merge (found on P008, T31).
            own_words = squash(written).lower() if written else None
            if own_words and f["name"] and f["name"].strip().lower() != own_words:
                notes.append(f"{label}: name '{f['name']}' changed to the record's words '{own_words}'")
            f["name"] = own_words or (f["name"].strip().lower() if f["name"] else None)

        # Flags: unverified if 3, 4 or 5 failed; missing_dose on a current medicine with no dose.
        if verified:
            flags.discard("unverified")
        else:
            flags.add("unverified")
        if f["type"] == "medicine" and f["status"] == "current" and not f["dose"]:
            flags.add("missing_dose")
        else:
            flags.discard("missing_dose")
        order = ["unverified", "missing_dose", "possible_missed", "unknown_name"]
        f["flags"] = [x for x in order if x in flags]

    return {"checked": out, "problems": problems, "notes": notes, "unknown": unknown}


def pick(first, second):
    """Of two checked tries, keep the one with fewer problems. The retry wins a tie.
    A try whose shape was wrong always loses to one whose shape was right."""
    def score(r):
        return (r["checked"] is None, len(r["problems"]))
    return second if score(second) <= score(first) else first


def check_with_retry(first_doc, source_text, extract_again):
    """For the extract step (T19/T20): check, and retry once only if the check fails.

    extract_again(problems) must make the one extra model call, save the reply as
    <P>_<H>.attempt2.json (attempt: 2), and return it as a dict. It is called at most once.
    Returns the kept result (see check_record) plus "attempt" (1 or 2) and "retried".
    """
    r1 = check_record(first_doc, source_text)
    if not r1["problems"]:
        return {**r1, "attempt": 1, "retried": False}
    second_doc = extract_again(r1["problems"])
    r2 = check_record(second_doc, source_text)
    kept = pick(r1, r2)
    return {**kept, "attempt": 2 if kept is r2 else 1, "retried": True}


# ---------------------------------------------------------------- command line

def find_source(patient_id, source_file):
    """The hospital record file the extraction was read from."""
    for split in ("demo", "working", "heldout", "reserve"):
        path = DATA / split / patient_id / source_file
        if path.exists():
            return path
    return None


def is_hidden(patient_id):
    """Held-out (P021-P100) and reserve (R...) patients: print counts only."""
    return patient_id.startswith("R") or (patient_id.startswith("P") and int(patient_id[1:]) > 20)


def run(run_id, patients=None):
    in_dir = OUTPUTS / "extracted" / run_id
    out_dir = OUTPUTS / "checked" / run_id
    if not in_dir.is_dir():
        sys.exit(f"No saved extractions in {in_dir.relative_to(REPO)}")
    firsts = sorted(p for p in in_dir.glob("*_[ABC].json"))
    if patients:
        firsts = [p for p in firsts if p.name.split("_")[0] in patients]
    out_dir.mkdir(parents=True, exist_ok=True)

    report = {"run_id": run_id, "records": {}, "needs_retry": [], "failed": []}
    for path in firsts:
        stem = path.stem                      # e.g. P001_A
        pid = stem.split("_")[0]
        first = _load_json(path)
        source_path = find_source(pid, first.get("source_file", ""))
        if source_path is None:
            report["failed"].append(stem)
            report["records"][stem] = {"error": "source record not found"}
            continue
        with open(source_path, encoding="utf-8", newline="") as fh:
            source_text = fh.read()

        r = check_record(first, source_text)
        attempt, retried = 1, False
        second_path = in_dir / f"{stem}.attempt2.json"
        if r["problems"] and second_path.exists():
            r2 = check_record(_load_json(second_path), source_text)
            kept = pick(r, r2)
            attempt, retried, r = (2 if kept is r2 else 1), True, kept
        elif r["problems"]:
            report["needs_retry"].append(stem)

        if r["checked"] is None:
            report["failed"].append(stem)     # neither try had the right shape: nothing to keep
        else:
            with open(out_dir / f"{stem}.json", "w", encoding="utf-8") as fh:
                json.dump(r["checked"], fh, indent=2, ensure_ascii=False)
                fh.write("\n")
        report["records"][stem] = {
            "attempt_kept": attempt, "retried": retried,
            "passed": not r["problems"], "problems": r["problems"], "notes": r["notes"],
            "facts": len(r["checked"]["facts"]) if r["checked"] else 0,
            "unverified": sum("unverified" in f["flags"] for f in r["checked"]["facts"]) if r["checked"] else 0,
            "unknown_name": r["unknown"],
        }

    with open(out_dir / "check_report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    # Print a summary. Problems are printed for demo and working patients only.
    recs = report["records"]
    print(f"Checked {len(recs)} records in run {run_id}")
    print(f"  passed: {sum(1 for r in recs.values() if r.get('passed'))}")
    print(f"  retried: {sum(1 for r in recs.values() if r.get('retried'))}")
    print(f"  need a retry (no attempt2 file yet): {len(report['needs_retry'])}")
    print(f"  could not be used: {len(report['failed'])}")
    for stem, r in recs.items():
        if r.get("passed", True) is False and not is_hidden(stem.split("_")[0]):
            for p in r["problems"]:
                print(f"  {stem}: {p}")
    if report["needs_retry"]:
        print("Needs retry:", " ".join(report["needs_retry"]))
    report_path = out_dir / "check_report.json"
    print(f"Report: {report_path.relative_to(REPO) if report_path.is_relative_to(REPO) else report_path}")
    return report


def main():
    ap = argparse.ArgumentParser(description="Check step (T22). Reads saved extractions only.")
    ap.add_argument("--run", required=True, help="run ID, e.g. 20261115-v1-sonnet-5-5")
    ap.add_argument("--patients", nargs="+", help="only these patient IDs")
    args = ap.parse_args()
    run(args.run, args.patients)


if __name__ == "__main__":
    main()
