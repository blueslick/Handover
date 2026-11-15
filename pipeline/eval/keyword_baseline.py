"""Keyword baseline (T24): the simplest extractor, kept only for comparison.

For each hospital record it looks for every drug name in shared/drug_list.csv and every
brand name in shared/brand_to_generic.csv (a brand becomes its generic name). Each match
becomes one fact with status current. The drug list's kind column decides allergy or
medicine: an allergy-only name (egg, fish, aspirin ...) is an allergy. Other names are
allergies only when their line says "allerg" (this covers ibuprofen and lisinopril, which
the list gives both kinds). No stop words, no dose-change logic, no negation handling.
Then stack_merge.py keeps every fact from every hospital.

Usage (from the repo root, with the project venv):
    .venv/bin/python pipeline/eval/keyword_baseline.py D001
    .venv/bin/python pipeline/eval/keyword_baseline.py --working      (P001 to P020)

Writes outputs/baseline_keyword/<patient>.json. Check it with shared/validate.py.
Only D001 and P001 to P020 are allowed. Held-out and reserve IDs are refused here,
so this script cannot open them.

Held-out mode (T65, Abby only, after the freeze):
    .venv/bin/python pipeline/eval/keyword_baseline.py --heldout --all-heldout
With --heldout the script first checks (pipeline/eval/heldout_guard.py) that the `freeze` tag
exists and that the output folder is git-ignored, and stops before opening any held-out file
if not. Output goes to outputs/results_heldout/baseline_keyword/ and the screen shows counts
only. The way facts are found is the same for every patient.
"""

import argparse
import csv
import re
from datetime import datetime
from pathlib import Path

import heldout_guard
from stack_merge import build_record, write_record

REPO = Path(__file__).resolve().parents[2]
SHARED = REPO / "shared"
OUT = REPO / "outputs" / "baseline_keyword"

# The patients allowed without --heldout. The held-out rules live in heldout_guard.py.
WORKING = heldout_guard.WORKING
ALLOWED = heldout_guard.OPEN_IDS

DATE_FORMATS = ["%Y-%m-%d", "%d %B %Y", "%d-%b-%Y"]
# A dose written straight after the name, e.g. "1 g", "5 mg" or "500 mg" after a comma.
DOSE_AFTER_NAME = re.compile(r"[\s,]*(\d+(?:\.\d+)?)\s*(mg|mcg|g|mL|units|puffs|drops)\b")


# Load every drug name and brand name. Each maps to its lowercase generic name.
def load_names():
    names = {}
    with (SHARED / "drug_list.csv").open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            name = row["name"].strip().lower()
            names[name] = name
    with (SHARED / "brand_to_generic.csv").open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            names[row["brand"].strip().lower()] = row["generic"].strip().lower()
    return names


# Read the drug list's kind column: for each generic name, the set of kinds it has
# ("medicine", "allergy", or both for ibuprofen and lisinopril).
def load_kinds():
    kinds = {}
    with (SHARED / "drug_list.csv").open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            kinds.setdefault(row["name"].strip().lower(), set()).add(row["kind"].strip().lower())
    return kinds


# Decide whether a matched name is an allergy or a medicine.
# An allergy-only word in the drug list (egg, fish, aspirin ...) is always an allergy.
# Otherwise (medicine-only names, and names listed as both) it is an allergy only when
# its line says "allerg", as in the first version of this baseline.
def classify_name(generic, line, kinds):
    if kinds.get(generic, set()) == {"allergy"}:
        return "allergy"
    if "allerg" in line.lower():
        return "allergy"
    return "medicine"


# One pattern that finds any name. Longest names first, so "amoxicillin / clavulanate"
# wins over "amoxicillin". The look-arounds stop a name matching inside a longer word.
def build_pattern(names):
    alternatives = sorted(names, key=len, reverse=True)
    body = "|".join(re.escape(a) for a in alternatives)
    return re.compile(rf"(?<![a-z0-9])(?:{body})(?![a-z0-9])", re.IGNORECASE)


# Turn a written visit date ("2021-03-02", "14 July 2021", "05-Oct-2021") into ISO form.
def to_iso(text):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"unrecognised visit date: {text!r}")


# Read the visit date each template prints. Every fact from that record gets this date.
def visit_date(path, hospital, text):
    if hospital == "A":
        rows = list(csv.DictReader(text.splitlines()))
        return to_iso(rows[0]["EncounterDate"])
    if hospital == "B":
        match = re.search(r"Date of visit:\s*(.+)", text)
    else:
        match = re.search(r"^\s*Date\s*:\s*(.+?)\s*$", text, re.MULTILINE)
    if not match:
        raise ValueError(f"no visit date found in {path.name}")
    return to_iso(match.group(1))


# Return the dose if one is written straight after the name; otherwise None.
def dose_after(line, position):
    found = DOSE_AFTER_NAME.match(line, position)
    if not found:
        return None
    return f"{found.group(1)} {found.group(2)}"


# Find every name in one hospital record and return facts in the extracted shape.
def extract_record(path, hospital, names, kinds, pattern):
    text = path.read_text(encoding="utf-8")
    date = visit_date(path, hospital, text)
    facts = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for match in pattern.finditer(line):
            written = match.group(0)
            generic = names[written.lower()]
            fact_type = classify_name(generic, line, kinds)
            # Only medicines carry a dose (the schema allows dose on medicine facts only).
            dose = dose_after(line, match.end()) if fact_type == "medicine" else None
            # A current medicine with no dose must carry missing_dose (validate.py rule).
            flags = ["missing_dose"] if fact_type == "medicine" and dose is None else []
            facts.append({
                "type": fact_type,
                "name": generic,
                "name_as_written": written,
                "dose": dose,
                "frequency": None,
                "reaction": None,
                "status": "current",
                "date": date,
                "quote": line,
                "flags": flags,
            })
    return facts


# Find one patient's three hospital records by name pattern. The key and Synthea files are never picked up.
def record_files(patient_id):
    folder = heldout_guard.patient_folder(patient_id)
    return sorted(p for p in folder.glob(f"{patient_id}_[ABC].*") if p.suffix in (".csv", ".txt"))


# Run the keyword pass on one patient and merge with stack_merge().
def run_patient(patient_id, names, kinds, pattern):
    files = record_files(patient_id)
    if len(files) != 3:
        raise SystemExit(f"{patient_id}: expected 3 hospital records, found {len(files)}")
    extractions = []
    for path in files:
        hospital = path.stem.split("_")[-1]
        extractions.append({
            "patient_id": patient_id,
            "hospital": hospital,
            "source_file": path.name,
            "facts": extract_record(path, hospital, names, kinds, pattern),
        })
    return build_record("baseline_keyword", patient_id, None, extractions)


def main():
    ap = argparse.ArgumentParser(description="Keyword baseline (T24). See the top of this file.")
    ap.add_argument("patients", nargs="*", help="e.g. D001 P001")
    ap.add_argument("--working", action="store_true", help="run P001 to P020")
    ap.add_argument("--out-dir", default=None,
                    help="where to write (default outputs/baseline_keyword; held-out default "
                         "outputs/results_heldout/baseline_keyword)")
    heldout_guard.add_heldout_args(ap)
    args = ap.parse_args()

    ids = list(args.patients) + (WORKING if args.working else [])
    if not ids and not args.all_heldout:
        ap.error("give patient IDs, or --working, or --all-heldout")
    # Refuse held-out IDs without --heldout, exactly as before.
    ids = list(dict.fromkeys(heldout_guard.pick_ids(ap, args, ids)))  # keep order, drop repeats
    out_dir = heldout_guard.pick_out_dir(args.out_dir, ids, OUT, "baseline_keyword")

    # Held-out guard: the freeze tag and a git-ignored folder, checked before any record is opened.
    hidden = heldout_guard.guard_run(ids, [out_dir / f"{pid}.json" for pid in ids])
    if hidden:
        heldout_guard.require_three_records(ids, record_files)

    names = load_names()
    kinds = load_kinds()
    pattern = build_pattern(names)
    total_facts = 0
    for pid in ids:
        record = run_patient(pid, names, kinds, pattern)
        out = out_dir / f"{pid}.json"
        write_record(record, out)
        heldout_guard.say(pid, len(record["facts"]), out, hidden)
        total_facts += len(record["facts"])
    if hidden:
        print(f"{len(ids)} patients, {total_facts} facts -> {out_dir}")


if __name__ == "__main__":
    main()
