"""Keyword baseline (T24): the simplest extractor, kept only for comparison.

For each hospital record it looks for every drug name in shared/drug_list.csv and every
brand name in shared/brand_to_generic.csv (a brand becomes its generic name). Each match
becomes one fact with status current. A match on a line that also contains "allerg"
becomes an allergy instead. No stop words, no dose-change logic, no negation handling.
Then stack_merge.py keeps every fact from every hospital.

Usage (from the repo root, with the project venv):
    .venv/bin/python pipeline/eval/keyword_baseline.py D001
    .venv/bin/python pipeline/eval/keyword_baseline.py --working      (P001 to P020)

Writes outputs/baseline_keyword/<patient>.json. Check it with shared/validate.py.
Only D001 and P001 to P020 are allowed. Held-out and reserve IDs are refused here,
so this script cannot open them.
"""

import argparse
import csv
import re
from datetime import datetime
from pathlib import Path

from stack_merge import build_record, write_record

REPO = Path(__file__).resolve().parents[2]
SHARED = REPO / "shared"
DATA = REPO / "pipeline" / "data"
OUT = REPO / "outputs" / "baseline_keyword"

WORKING = [f"P{n:03d}" for n in range(1, 21)]
ALLOWED = ["D001"] + WORKING
# Folder under pipeline/data/ for each kind of patient. R (reserve) is deliberately absent.
FOLDER = {"D": "demo", "P": "working"}

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
def extract_record(path, hospital, names, pattern):
    text = path.read_text(encoding="utf-8")
    date = visit_date(path, hospital, text)
    facts = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        allergy_line = "allerg" in line.lower()
        for match in pattern.finditer(line):
            written = match.group(0)
            if allergy_line:
                fact_type, dose = "allergy", None
            else:
                fact_type, dose = "medicine", dose_after(line, match.end())
            # A current medicine with no dose must carry missing_dose (validate.py rule).
            flags = ["missing_dose"] if fact_type == "medicine" and dose is None else []
            facts.append({
                "type": fact_type,
                "name": names[written.lower()],
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
    folder = DATA / FOLDER[patient_id[0]] / patient_id
    return sorted(p for p in folder.glob(f"{patient_id}_[ABC].*") if p.suffix in (".csv", ".txt"))


# Run the keyword pass on one patient and merge with stack_merge().
def run_patient(patient_id, names, pattern):
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
            "facts": extract_record(path, hospital, names, pattern),
        })
    return build_record("baseline_keyword", patient_id, None, extractions)


def main():
    ap = argparse.ArgumentParser(description="Keyword baseline (T24). See the top of this file.")
    ap.add_argument("patients", nargs="*", help="e.g. D001 P001")
    ap.add_argument("--working", action="store_true", help="run P001 to P020")
    ap.add_argument("--out-dir", default=str(OUT), help="where to write (default outputs/baseline_keyword)")
    args = ap.parse_args()

    ids = list(args.patients) + (WORKING if args.working else [])
    if not ids:
        ap.error("give patient IDs, or --working")
    for pid in ids:
        if pid not in ALLOWED:
            ap.error(f"{pid} is not allowed: only D001 and P001-P020 (held-out and reserve IDs are refused)")

    names = load_names()
    pattern = build_pattern(names)
    for pid in dict.fromkeys(ids):  # keep order, drop repeats
        record = run_patient(pid, names, pattern)
        out = Path(args.out_dir) / f"{pid}.json"
        write_record(record, out)
        print(f"{pid}: {len(record['facts'])} facts -> {out}")


if __name__ == "__main__":
    main()
