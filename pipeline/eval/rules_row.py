"""Rules row (T24): the keyword baseline's facts, compiled by Daniel's compile_patient(). Removable.

This is a team proposal, kept as its own row. It needs no model and no API key, and it
does not read Claude's saved extractions.

For each hospital record (A, B, C) the keyword pass (keyword_baseline.py) finds the facts.
The three records go to compile_patient() from pipeline/tool/compile.py as they are, in
one list. That function is Daniel's and is only called here, never edited. Its result is
written to outputs/baseline_rules_row/<P>.json with kind "baseline_rules_row" (compile_patient
returns kind "compiled", so the kind is set here; shared/schema lists this kind).

To remove the row: delete this file, its test, and outputs/baseline_rules_row/.

Usage (from the repo root):
    .venv/bin/python pipeline/eval/rules_row.py D001
    .venv/bin/python pipeline/eval/rules_row.py P001 P002 ...

Held-out mode (T65, Abby only, after the freeze): add --heldout and the IDs, or --all-heldout for
all 160. With no IDs and no --all-heldout the script stops with an error. It first checks
(pipeline/eval/heldout_guard.py) that the `freeze` tag exists and that the output folder is
git-ignored, and stops before opening any held-out file if not. Output goes to
outputs/results_heldout/baseline_rules_row/ and the screen shows counts only.
"""

import argparse
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parent
TOOL = EVAL.parent / "tool"  # pipeline/tool, where Daniel's compile.py lives
sys.path.insert(0, str(TOOL))

from compile import compile_patient  # noqa: E402  (Daniel's compile step, called unchanged)

import heldout_guard  # noqa: E402
from keyword_baseline import (  # noqa: E402
    build_pattern, extract_record, load_kinds, load_names, record_files,
)
from stack_merge import write_record  # noqa: E402

REPO = EVAL.parents[1]
OUT = REPO / "outputs" / "baseline_rules_row"
# The kind written into each record (listed in shared/schema/compiled.schema.json).
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
    ap.add_argument("patients", nargs="*", help="e.g. D001 P001")
    ap.add_argument("--out-dir", default=None,
                    help="where to write (default outputs/baseline_rules_row; held-out default "
                         "outputs/results_heldout/baseline_rules_row)")
    heldout_guard.add_heldout_args(ap)
    args = ap.parse_args()

    # Never run on nothing: IDs are needed, or --all-heldout.
    if not args.patients and not args.all_heldout:
        ap.error("give patient IDs, or --all-heldout")
    # Refuse held-out IDs without --heldout, exactly as before.
    ids = list(dict.fromkeys(heldout_guard.pick_ids(ap, args, args.patients)))  # keep order, drop repeats
    out_dir = heldout_guard.pick_out_dir(args.out_dir, ids, OUT, "baseline_rules_row")

    # Held-out guard: the freeze tag and a git-ignored folder, checked before any record is opened.
    hidden = heldout_guard.guard_run(ids, [out_dir / f"{pid}.json" for pid in ids])
    if hidden:
        heldout_guard.require_three_records(ids, record_files)

    names = load_names()
    kinds = load_kinds()
    pattern = build_pattern(names)
    total_facts = 0
    for pid in ids:
        record = build_rules_row(pid, names, kinds, pattern)
        out = out_dir / f"{pid}.json"
        write_record(record, out)
        heldout_guard.say(pid, len(record["facts"]), out, hidden)
        total_facts += len(record["facts"])
    if hidden:
        print(f"{len(ids)} patients, {total_facts} facts -> {out_dir}")


if __name__ == "__main__":
    main()
