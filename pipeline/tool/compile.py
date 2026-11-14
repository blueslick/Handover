"""Compile step (T23): merge one patient's checked hospital records into one record.

Section 7 of docs/Handover_Pipeline_and_Frontend_Plan.md. No model calls: this
reads saved files only (CLAUDE.md, Model calls).

This is the tool's own copy of the six compile rules. It is written separately
from pipeline/data/make_answer_key.py on purpose, so the tool is never scored
against its own code. Both follow the plan and the four rule calls in
docs/decisions.md (T14).

The six rules, and where each one lives below:

  1. Same drug, one fact.   canonical_name() turns brands into generics; group_entries()
                            puts every mention of a drug into one group; all hospitals
                            stating the current value become `sources`.
  2. Explicit stop.         compile_group(): a later "stopped" entry wins; the earlier
                            "current" entry goes into `history`.
  3. Dose change.           compile_group(): a later dated dose wins; the earlier dose
                            goes into `history`; finish_fact() adds the `dose_changed` flag.
  4. Silence is not a stop. Nothing to do: a record that doesn't mention a drug gives no
                            entry, so the fact keeps the hospital and date it was last seen.
  5. Allergy vs NKA.        no_known_conflicts(): "no known allergies" and any recorded
                            allergy are both kept, side by side, as a conflict.
  6. Any other disagreement compile_group(): disagreements nothing settles are kept on
     on a critical fact.    every side and flagged as a conflict (see the allergy note).

Calls this file makes that the plan leaves open (also in docs/decisions.md, T23):

  * Allergies: any disagreement between hospitals about the same allergy (status or
    reaction) is a conflict, whatever the dates. Rules 2 and 3 are about medicines, so
    nothing "settles" an allergy, and a later record must never quietly turn an
    allergy into "side effect" or "suspected" (rules 5 and 6).
  * Medicines and diagnoses: a later dated value wins (rules 2 and 3); different values
    on the same latest date are a conflict (decisions.md, T14 call 1).
  * "No known allergies" conflicts with allergies recorded as current or suspected, not
    with "side effect, not an allergy" (that isn't an allergy).
  * "No regular medicines" conflicts with a current medicine first recorded on or before
    that date; one first recorded later is a new start (T14 call 3).
  * A stopped medicine shows the last dose it was taken at (T14 call 4).
  * A blank dose, frequency or reaction means "not stated", never a change.
  * Reactions are compared by their words, not punctuation: "hay fever symptoms; hives"
    and "hay fever symptoms, hives" are the same reaction.
  * Doses are tidied before comparing: "1 g" becomes "1000 mg", "5.0 mg" becomes "5 mg".
  * A fact with no date takes the latest date of the other facts in the same record
    (the visit date is the latest date a record prints). If the record has no dates at
    all, the fact stays undated and counts as the oldest.
  * A name not in the brand table or the drug list is kept as written, with the
    `unknown_name` flag. Never guessed (plan, gap 5).

How to call it (for Abby's tests, T17):

    from compile import compile_patient          # with pipeline/tool on the path
    record = compile_patient("P001", [extracted_A, extracted_B, extracted_C])

Each item is one checked record in the extracted shape
(shared/schema/extracted.schema.json): a dict with `hospital`, `source_file` and
`facts`; the other wrapper fields are optional here. The result is one compiled
record (shared/schema/compiled.schema.json), `kind: compiled`.

Command line:

    python pipeline/tool/compile.py --run <run_id>                 every patient in the run
    python pipeline/tool/compile.py --run <run_id> --patients P001 P002
    python pipeline/tool/compile.py --run <run_id> --input extracted   (skip the Check step's folder)

Reads outputs/checked/<run_id>/P001_A.json (and _B, _C), writes
outputs/compiled/<run_id>/P001.json, and validates every file it writes.
Held-out and reserve patients: only IDs and counts are printed, never contents
(CLAUDE.md, Held-out patients).
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parent
REPO = TOOL.parent.parent
SHARED = REPO / "shared"
OUTPUTS = REPO / "outputs"

TYPE_ORDER = {"allergy": 0, "medicine": 1, "diagnosis": 2, "operation": 3}
DRUG_TYPES = {"allergy", "medicine"}
CARRIED_FLAGS = ("unverified", "possible_missed", "unknown_name")  # from the Check step
UNDATED = "0000-00-00"  # sorts before every real date


# ---------------------------------------------------------------- tables

def load_tables():
    """Brand table (brand -> generic) and the set of generic names on the drug list."""
    brands, generics = {}, set()
    with open(SHARED / "brand_to_generic.csv", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            brands[row["brand"].strip().lower()] = row["generic"].strip().lower()
    with open(SHARED / "drug_list.csv", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            generics.add(row["name"].strip().lower())
    generics.update(brands.values())
    return brands, generics


_TABLES = None


def tables():
    global _TABLES
    if _TABLES is None:
        _TABLES = load_tables()
    return _TABLES


# ---------------------------------------------------------------- tidying one fact

def tidy(text):
    return re.sub(r"\s+", " ", text.strip().lower()) if text else None


def canonical_name(fact):
    """Rule 1, first half: the generic name this fact is about.

    Returns (name, unknown). unknown=True means neither the name nor the name as
    written is a known drug, so the fact keeps its written name and is flagged.
    """
    if fact["status"] == "none_recorded":
        return None, False
    name, written = tidy(fact.get("name")), tidy(fact.get("name_as_written"))
    if fact["type"] not in DRUG_TYPES:
        return (name or written), False      # diagnoses and operations: no drug tables
    brands, generics = tables()
    for candidate in (name, written):
        if candidate and candidate in brands:
            return brands[candidate], False
        if candidate and candidate in generics:
            return candidate, False
    if name and "unknown_name" not in fact.get("flags", []):
        return name, False                   # the Check step accepted this name
    return None, True


def tidy_dose(dose):
    """'1 g' -> '1000 mg', '5.0 mg' -> '5 mg'. Anything else is returned as written."""
    if not dose:
        return None
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(\S+)\s*", dose)
    if not m:
        return dose
    number, unit = float(m.group(1)), m.group(2)
    if unit == "g":
        number, unit = number * 1000, "mg"
    text = f"{number:.3f}".rstrip("0").rstrip(".")
    return f"{text} {unit}"


def entries_from_record(record):
    """Turn one checked record into entries: facts tagged with hospital and file."""
    hosp, fname = record["hospital"], record["source_file"]
    dated = [f["date"] for f in record["facts"] if f.get("date")]
    fallback = max(dated) if dated else None
    out = []
    for f in record["facts"]:
        name, unknown = canonical_name(f)
        flags = [x for x in f.get("flags", []) if x in CARRIED_FLAGS]
        if unknown and "unknown_name" not in flags:
            flags.append("unknown_name")
        is_med = f["type"] == "medicine"
        out.append({
            "type": f["type"], "status": f["status"],
            "name": name,
            # Unknown names are grouped by how they were written, so two hospitals
            # writing the same unknown name still make one fact (rule 1).
            "group_name": name or (None if f["status"] == "none_recorded"
                                   else "?" + (tidy(f.get("name_as_written")) or "")),
            "name_as_written": f.get("name_as_written"),
            "dose": tidy_dose(f.get("dose")) if is_med else None,
            "frequency": f.get("frequency") if is_med else None,
            "reaction": f.get("reaction") if f["type"] == "allergy" else None,
            "date": f.get("date") or fallback,
            "quote": f.get("quote"),
            "flags": flags,
            "hospital": hosp, "file": fname,
        })
    return out


def when(e):
    return (e["date"] or UNDATED, e["hospital"])


# ---------------------------------------------------------------- comparing values

def agrees(a, b):
    """Same status, and no stated value that differs. Blank means 'not stated'."""
    if a["status"] != b["status"]:
        return False
    if a["dose"] and b["dose"] and a["dose"] != b["dose"]:
        return False
    if a["frequency"] and b["frequency"] and a["frequency"] != b["frequency"]:
        return False
    if a["reaction"] and b["reaction"] and reaction_words(a["reaction"]) != reaction_words(b["reaction"]):
        return False
    return True


def reaction_words(text):
    """Hospitals punctuate reactions differently ('hives; rash', 'hives, rash',
    'hives and rash'). Compare the words, not the punctuation."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return frozenset(w for w in words if w not in {"and", "or", "causes", "which"})


def stated(entries, field):
    """The most recent value of a field that any of these entries states."""
    for e in sorted(entries, key=when, reverse=True):
        if e[field]:
            return e[field]
    return None


def summary(entries):
    """One entry standing for a set of agreeing entries."""
    return {"status": entries[0]["status"], "dose": stated(entries, "dose"),
            "frequency": stated(entries, "frequency"), "reaction": stated(entries, "reaction")}


def cluster(entries):
    """Split entries into sets that agree with each other, in date order."""
    sets = []
    for e in sorted(entries, key=when):
        home = next((s for s in sets if agrees(e, summary(s))), None)
        if home is not None:
            home.append(e)
        else:
            sets.append([e])
    return sets


# ---------------------------------------------------------------- one drug / allergy / diagnosis

def history_item(entries):
    last = max(entries, key=when)
    s = summary(entries)
    return {"status": s["status"], "dose": s["dose"], "frequency": s["frequency"],
            "hospital": last["hospital"], "date": last["date"], "quote": last["quote"]}


def compile_group(entries):
    """Rules 1, 2, 3, 4 and 6 for every mention of one name.

    Returns a list of (current_entries, history) pairs: one pair normally, several
    when the hospitals disagree and nothing settles it (rule 6).
    """
    if entries[0]["type"] == "allergy":
        # Nothing settles an allergy disagreement: every different version is kept.
        sides = cluster(entries)
        return [(side, []) for side in sides]

    by_date = {}
    for e in entries:
        by_date.setdefault(e["date"] or UNDATED, []).append(e)
    dates = sorted(by_date)
    latest = cluster(by_date[dates[-1]])
    if len(latest) > 1:
        # Rule 6: different values on the same latest date. Keep every side; what
        # came before is history on each side.
        earlier = [e for d in dates[:-1] for e in by_date[d]]
        history = [history_item(r) for r in runs(earlier)]
        return [(side, list(history)) for side in latest]

    # Rules 2 and 3: the latest value wins. Earlier entries saying the same thing
    # are extra sources (rule 1); earlier different values become history.
    current = latest[0]
    earlier = sorted((e for d in dates[:-1] for e in by_date[d]), key=when)
    while earlier and agrees(earlier[-1], summary(current)):
        current.insert(0, earlier.pop())
    history = [history_item(r) for r in runs(earlier)]
    return [(current, history)]


def runs(entries):
    """Consecutive agreeing entries, oldest first, for the history list."""
    out = []
    for e in sorted(entries, key=when):
        if out and agrees(e, summary(out[-1])):
            out[-1].append(e)
        else:
            out.append([e])
    return out


def finish_fact(patient_id, current, history):
    """Build one compiled fact from the entries that state its current value."""
    latest = max(current, key=when)
    s = summary(current)
    ftype = latest["type"]
    dose, freq = s["dose"], s["frequency"]
    if ftype == "medicine" and s["status"] == "stopped" and not dose:
        # A stop note rarely repeats the dose: show the last dose it was taken at.
        for h in reversed(history):
            if h["dose"]:
                dose, freq = h["dose"], freq or h["frequency"]
                break
    flags = []
    for e in current:
        for x in e["flags"]:
            if x not in flags:
                flags.append(x)
    if ftype == "medicine" and s["status"] == "current":
        if not dose:
            flags.append("missing_dose")
        if any(h["status"] == "current" and h["dose"] and h["dose"] != dose for h in history):
            flags.append("dose_changed")          # rule 3
    written = next((e["name_as_written"] for e in sorted(current, key=when, reverse=True)
                    if e["name_as_written"]), None)
    return {
        "fact_id": None, "patient_id": patient_id, "type": ftype,
        "name": latest["name"], "name_as_written": written,
        "dose": dose if ftype == "medicine" else None,
        "frequency": freq if ftype == "medicine" else None,
        "reaction": s["reaction"] if ftype == "allergy" else None,
        "status": s["status"], "hospital": latest["hospital"],
        "date": latest["date"], "quote": latest["quote"],
        "sources": [{"hospital": e["hospital"], "date": e["date"], "quote": e["quote"],
                     "file": e["file"]} for e in sorted(current, key=when)],
        "history": history, "flags": flags, "conflict_group": None,
    }


# ---------------------------------------------------------------- "no known allergies" / "no regular medicines"

def no_known_conflicts(none_fact, facts):
    """Rules 5 and 6 for a 'none recorded' fact: which facts it disagrees with."""
    if none_fact["type"] == "allergy":
        return [f for f in facts if f["type"] == "allergy" and f["status"] in ("current", "suspected")]
    if none_fact["type"] == "medicine":
        said_none = none_fact["date"] or UNDATED
        return [f for f in facts if f["type"] == "medicine" and f["status"] == "current"
                and min(s["date"] or UNDATED for s in f["sources"]) <= said_none]
    return []


# ---------------------------------------------------------------- one patient

def compile_patient(patient_id, records, run_id=None):
    """Merge a patient's checked records into one compiled record (kind 'compiled')."""
    if not records:
        raise ValueError(f"{patient_id}: no records to compile")
    groups, nones, built_from = {}, {}, []
    for record in records:
        built_from.append(record["source_file"])
        for e in entries_from_record(record):
            if e["status"] == "none_recorded":
                nones.setdefault(e["type"], []).append(e)
            else:
                groups.setdefault((e["type"], e["group_name"]), []).append(e)

    facts, conflicts = [], []
    for key in groups:
        made = [finish_fact(patient_id, cur, hist) for cur, hist in compile_group(groups[key])]
        facts.extend(made)
        if len(made) > 1:
            conflicts.append(made)

    named = list(facts)
    for ftype, entries in nones.items():
        # Several hospitals saying "none" is one fact with several sources (rule 1).
        none_fact = finish_fact(patient_id, entries, [])
        facts.append(none_fact)
        against = no_known_conflicts(none_fact, named)
        if against:
            conflicts.append([none_fact] + against)

    # A fact can be in two disagreements (an allergy that differs between hospitals
    # and also clashes with "no known allergies"): join those into one group.
    joined = []
    for c in conflicts:
        overlapping = [j for j in joined if any(f is g for f in c for g in j)]
        for j in overlapping:
            joined.remove(j)
            c = j + [f for f in c if not any(f is g for g in j)]
        joined.append(c)

    facts.sort(key=lambda f: (TYPE_ORDER[f["type"]], f["name"] is None,
                              f["name"] or f["name_as_written"] or "", f["status"],
                              f["date"] or UNDATED, f["hospital"]))
    for n, f in enumerate(facts, 1):
        f["fact_id"] = f"{patient_id}-F{n:02d}"
    position = {id(f): i for i, f in enumerate(facts)}
    joined.sort(key=lambda c: min(position[id(f)] for f in c))
    for n, c in enumerate(joined, 1):
        for f in c:
            f["conflict_group"] = f"{patient_id}-C{n}"
            if "conflict" not in f["flags"]:
                f["flags"].append("conflict")

    return {"format_version": "1.0", "kind": "compiled", "patient_id": patient_id,
            "run_id": run_id, "built_from": sorted(built_from), "facts": facts}


# ---------------------------------------------------------------- command line

def is_hidden(patient_id):
    """Held-out and reserve patients: never print their contents."""
    return patient_id.startswith("R") or (patient_id.startswith("P") and int(patient_id[1:]) > 20)


def validate(record):
    sys.path.insert(0, str(SHARED))
    import validate as v  # shared/validate.py
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
        json.dump(record, fh)
        tmp = fh.name
    try:
        return v.check_file(tmp, "compiled")
    finally:
        Path(tmp).unlink()


def main():
    ap = argparse.ArgumentParser(description="Compile checked records into one record per patient (T23).")
    ap.add_argument("--run", required=True, help="run ID (folder name under outputs/)")
    ap.add_argument("--patients", nargs="+", help="only these patients (default: all in the run)")
    ap.add_argument("--input", default="checked", choices=["checked", "extracted"],
                    help="which outputs/ folder to read (default: checked)")
    args = ap.parse_args()

    src = OUTPUTS / args.input / args.run
    dst = OUTPUTS / "compiled" / args.run
    if not src.is_dir():
        sys.exit(f"No folder {src.relative_to(REPO)}")
    files = sorted(p for p in src.glob("*_[ABC].json"))
    by_patient = {}
    for p in files:
        by_patient.setdefault(p.stem.split("_")[0], []).append(p)
    wanted = args.patients or sorted(by_patient)

    dst.mkdir(parents=True, exist_ok=True)
    done, failed, hidden = 0, [], 0
    for pid in wanted:
        paths = by_patient.get(pid)
        if not paths:
            failed.append(f"{pid}: no records in {src.relative_to(REPO)}")
            continue
        records = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
        record = compile_patient(pid, records, run_id=args.run)
        problems = validate(record)
        if problems:
            failed.append(f"{pid}: compiled record failed the format check"
                          + ("" if is_hidden(pid) else ": " + "; ".join(problems[:3])))
            continue
        (dst / f"{pid}.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                                         encoding="utf-8")
        done += 1
        if is_hidden(pid):
            hidden += 1
        else:
            n_conf = len({f["conflict_group"] for f in record["facts"] if f["conflict_group"]})
            print(f"{pid}: {len(record['facts'])} facts, {n_conf} conflicts")
    if hidden:
        print(f"{hidden} held-out/reserve patients compiled (contents not shown)")
    print(f"Wrote {done} compiled records to {dst.relative_to(REPO)}")
    for line in failed:
        print("FAILED", line)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
