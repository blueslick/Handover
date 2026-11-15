"""Omission-check line for the held-out table (T37). Not a build-up row: it sits under the table.

Usage (from the repo root, with the project venv):
    .venv/bin/python pipeline/eval/omission_line.py

Reads two things that other scripts already wrote, and makes no model calls:
  - the omission flags for the full-tool run: outputs/results_heldout/omission/<run_id>/*.json
    (omission_check.py: a possible_missed flag means a drug name or allergy word is in a hospital
    record but the saved extraction has no fact with that generic name)
  - row 7's failures: outputs/results_heldout/scores/row7/{heldout,reserve}/failures.csv
    (score.py: every missed case and every wrong-status case, with the key fact's generic name)

Then it counts how often a flag sat on the same patient and the same generic name as a row 7
miss, so the write-up can say "the check would have pointed at X of Y real misses, and raised
Z flags that were not real misses".

Two kinds of row 7 miss are counted:
  missed        the compiled record has no fact with that name at all. This is what the check
                is built to find.
  wrong_status  the name is there but with the wrong status. The check does not look at status,
                so it can only point at one by accident (a different hospital record may have
                left the name out).
For the "name left out" misses it also counts by fact type (allergy, medicine, diagnosis,
operation) and by whether the name is in shared/drug_list.csv or shared/brand_to_generic.csv (as a
brand or as a generic name). The check can only look for names in those two lists, so a name in
neither list is one it cannot see.
Writes outputs/results/heldout/omission_line.csv: counts only, no IDs, no names.
"""

import csv
import json
import sys
from pathlib import Path

import heldout_guard

REPO = Path(__file__).resolve().parents[2]
RUN_ID = "20261115-v2-heldout-sonnet-5-5"
OMISSION_DIR = REPO / "outputs" / "results_heldout" / "omission" / RUN_ID
SCORES_DIR = REPO / "outputs" / "results_heldout" / "scores" / "row7"
OUT_FILE = REPO / "outputs" / "results" / "heldout" / "omission_line.csv"
SHARED = REPO / "shared"
MISS_KINDS = ("missed", "wrong_status")
FACT_TYPES = ("allergy", "medicine", "diagnosis", "operation")


class OmissionLineError(Exception):
    """A check failed. The message gives counts only."""


def _is_true(text):
    return str(text).strip().lower() == "true"


# Every possible_missed flag as (patient, generic name), one per flag, plus record counts.
def read_flags(omission_dir):
    flags, records, records_with_flag = [], 0, 0
    for path in sorted(Path(omission_dir).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        records += 1
        records_with_flag += bool(data["flags"])
        for flag in data["flags"]:
            flags.append((data["patient_id"], flag["generic"].strip().lower()))
    return flags, records, records_with_flag


# The names the omission check can look for: drug_list.csv names, and brand_to_generic.csv brands and generics.
def read_name_lists(shared_dir=SHARED):
    with open(Path(shared_dir) / "drug_list.csv", encoding="utf-8", newline="") as handle:
        drug_list = {row["name"].strip().lower() for row in csv.DictReader(handle)}
    with open(Path(shared_dir) / "brand_to_generic.csv", encoding="utf-8", newline="") as handle:
        brand_table = set()
        for row in csv.DictReader(handle):
            brand_table |= {row["brand"].strip().lower(), row["generic"].strip().lower()}
    return drug_list, brand_table


# Row 7's missed and wrong-status cases as (patient, name, kind, is_critical, fact type) from failures.csv.
def read_misses(scores_dir):
    misses = []
    for part in ("heldout", "reserve"):
        path = Path(scores_dir) / part / "failures.csv"
        with open(path, encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["kind"] in MISS_KINDS:
                    misses.append((row["patient_id"], (row["name"] or "").strip().lower(),
                                   row["kind"], _is_true(row["key_critical"]), row["type"]))
    return misses


# Work out every count. Pure function of the two lists, so a test can feed made-up ones.
def compute(flags, records, records_with_flag, misses, name_lists=None):
    flag_pairs = set(flags)
    miss_pairs = {(m[0], m[1]) for m in misses}

    def pointed(kind=None, critical=None):
        chosen = [m for m in misses
                  if (kind is None or m[2] == kind) and (critical is None or m[3] == critical)]
        return sum((m[0], m[1]) in flag_pairs for m in chosen), len(chosen)

    flags_on_misses = sum(pair in miss_pairs for pair in flags)
    lines = [
        ("records_checked", records),
        ("possible_missed_flags", len(flags)),
        ("records_with_a_flag", records_with_flag),
        ("patients_with_a_flag", len({p for p, _ in flags})),
        ("distinct_patient_name_flags", len(flag_pairs)),
    ]
    for label, kind, critical in (("all_misses", None, None), ("name_absent_misses", "missed", None),
                                  ("wrong_status_misses", "wrong_status", None),
                                  ("critical_misses", None, True)):
        hit, total = pointed(kind, critical)
        lines += [(f"row7_{label}", total), (f"row7_{label}_pointed_at_by_a_flag", hit)]
    lines += [
        ("flags_on_a_row7_miss", flags_on_misses),
        ("flags_not_on_a_row7_miss", len(flags) - flags_on_misses),
    ]
    # The "name left out" misses, by fact type and by whether the check's name lists know the name.
    absent = [m for m in misses if m[2] == "missed"]
    for fact_type in FACT_TYPES:
        lines.append((f"row7_name_absent_type_{fact_type}", sum(m[4] == fact_type for m in absent)))
    if name_lists is not None:
        drug_list, brand_table = name_lists
        in_drugs = [m[1] in drug_list for m in absent]
        in_brands = [m[1] in brand_table for m in absent]
        lines += [
            ("row7_name_absent_in_drug_list", sum(in_drugs)),
            ("row7_name_absent_in_brand_table", sum(in_brands)),
            ("row7_name_absent_in_both_lists", sum(a and b for a, b in zip(in_drugs, in_brands))),
            ("row7_name_absent_in_neither_list", sum(not a and not b for a, b in zip(in_drugs, in_brands))),
        ]
    return lines


def write_line(lines, out_file):
    out_file = Path(out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["measure", "count"])
        writer.writerows(lines)


def main():
    # Held-out files are opened below, so the freeze tag is checked first.
    heldout_guard.require_freeze_tag()
    try:
        flags, records, with_flag = read_flags(OMISSION_DIR)
        misses = read_misses(SCORES_DIR)
    except FileNotFoundError as error:
        raise SystemExit(f"stopped: a needed file is missing ({Path(error.filename).parent.name}); "
                         "run omission_check.py and score.py first")
    lines = compute(flags, records, with_flag, misses, read_name_lists())
    write_line(lines, OUT_FILE)
    for name, count in lines:
        print(f"{name:<42}{count:>6}")
    print(f"Wrote {OUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
