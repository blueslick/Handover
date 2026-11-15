"""Rules row (T24): the keyword baseline's facts, compiled by Daniel's compile_patient(). Removable.

This is a team proposal, kept as its own row. It needs no model and no API key, and it
does not read Claude's saved extractions.

For each hospital record (A, B, C) the keyword pass (keyword_baseline.py) finds the facts.
The three records go to compile_patient() from pipeline/tool/compile.py as they are, in
one list. That function is Daniel's and is only called here, never edited. Its result is
written to outputs/baseline_rules_row/<P>.json with kind "baseline_rules_row" (compile_patient
returns kind "compiled", so the kind is set here; shared/schema does not list this kind yet).

To remove the row: delete this file, its test, and outputs/baseline_rules_row/.

Usage (from the repo root):
    .venv/bin/python pipeline/eval/rules_row.py D001
    .venv/bin/python pipeline/eval/rules_row.py P001 P002 ...
"""

import argparse
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parent
TOOL = EVAL.parent / "tool"  # pipeline/tool, where Daniel's compile.py lives
sys.path.insert(0, str(TOOL))

from compile import compile_patient  # noqa: E402  (Daniel's compile step, called unchanged)

from keyword_baseline import (  # noqa: E402
    ALLOWED, build_pattern, extract_record, load_kinds, load_names, record_files,
)
from stack_merge import write_record  # noqa: E402

REPO = EVAL.parents[1]
OUT = REPO / "outputs" / "baseline_rules_row"
# The kind written into each record. shared/schema/compiled.schema.json does not list it yet,
# so validate.py rejects these files on the kind until the team adds it (a shared/ change; team decision).
KIND = "baseline_rules_row"


# One extracted-shape record per hospital record, facts from the keyword pass, nothing merged.
def keyword_records(patient_id, names, kinds, pattern):
    files = record_files(patient_id)
    if len(files) != 3:
        raise SystemExit(f"{patient_id}: expected 3 hospital records, found {len(files)}")
    records = []
    for path in files:
        hospital = path.stem.split("_")[-1]
        records.append({
            "patient_id": patient_id,
            "hospital": hospital,
            "source_file": path.name,
            "facts": extract_record(path, hospital, names, kinds, pattern),
        })
    return records


# Build one patient's rules-row record: keyword facts per hospital, passed unchanged to compile_patient().
def build_rules_row(patient_id, names, kinds, pattern):
    records = keyword_records(patient_id, names, kinds, pattern)
    record = compile_patient(patient_id, records)
    record["kind"] = KIND
    return record


def main():
    ap = argparse.ArgumentParser(description="Rules row (T24): keyword facts through compile_patient(). No API.")
    ap.add_argument("patients", nargs="+", help="e.g. D001 P001")
    ap.add_argument("--out-dir", default=str(OUT), help="where to write (default outputs/baseline_rules_row)")
    args = ap.parse_args()

    for pid in args.patients:
        if pid not in ALLOWED:
            ap.error(f"{pid} is not allowed: only D001 and P001-P020 (held-out and reserve IDs are refused)")

    names = load_names()
    kinds = load_kinds()
    pattern = build_pattern(names)
    for pid in dict.fromkeys(args.patients):  # keep order, drop repeats
        record = build_rules_row(pid, names, kinds, pattern)
        out = Path(args.out_dir) / f"{pid}.json"
        write_record(record, out)
        print(f"{pid}: {len(record['facts'])} facts -> {out}")


if __name__ == "__main__":
    main()
