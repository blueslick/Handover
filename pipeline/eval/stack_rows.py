"""Build-up rows 4, 5 and 6 (T65): stack Claude's saved extractions, no merge rules, no model calls.

stack_merge.py has no command line of its own, so this runner feeds it. For each patient it
reads the three saved hospital files, stacks every fact with stack_merge.build_record(), and
writes one compiled-shape record per patient (kind "compiled", run_id = the run it was built from).

    Row 4  plain lists            outputs/extracted/<plain run>/<ID>_<A|B|C>.json
    Row 5  labels, first tries    outputs/extracted/<v2 run>/<ID>_<A|B|C>.json
    Row 6  labels + check         outputs/checked/<v2 run>/<ID>_<A|B|C>.json

Only that exact file name is read. A retry is saved as <ID>_<H>.attempt2.json, which this runner
never opens, so every row uses first tries only. If any patient is missing any of its 3 files the
runner stops before writing anything and says how many.

Usage (from the repo root):
    .venv/bin/python pipeline/eval/stack_rows.py --row 4 --run-id 20261115-v2-plain-sonnet-5-5 \\
        --working --out-dir /path/to/scratch/row4

Working and demo output needs an explicit --out-dir (use a scratch folder outside the repo).
Held-out mode (Abby only, after the freeze): add --heldout and the IDs, or --all-heldout. The script
first checks (pipeline/eval/heldout_guard.py) that the `freeze` tag exists and that the output
folder is git-ignored, and stops before opening any held-out file if not. Output then defaults to
outputs/results_heldout/row4|row5|row6/ and the screen shows counts only.
"""

import argparse
import json
from pathlib import Path

import heldout_guard
from stack_merge import build_record, write_record

REPO = Path(__file__).resolve().parents[2]
EXTRACTED = REPO / "outputs" / "extracted"
CHECKED = REPO / "outputs" / "checked"

# Which folder each row reads from. Rows 4 and 5 read extractions; row 6 reads the checked files.
ROW_SOURCE = {4: EXTRACTED, 5: EXTRACTED, 6: CHECKED}
# No new kind name (Q12): the stacked record uses the existing "compiled" kind.
KIND = "compiled"
HOSPITALS = ("A", "B", "C")


# The three saved files for one patient, by their exact names. Nothing is matched by pattern,
# so an attempt2 file can never be picked up.
def saved_paths(source_root, run_id, patient_id):
    folder = Path(source_root) / run_id
    return [folder / f"{patient_id}_{hospital}.json" for hospital in HOSPITALS]


# For each patient, the saved files that do not exist. Only patients with something missing are listed.
def find_missing(source_root, run_id, ids):
    missing = {}
    for pid in ids:
        absent = [path.name for path in saved_paths(source_root, run_id, pid) if not path.exists()]
        if absent:
            missing[pid] = absent
    return missing


# Read one saved file and make sure it is the patient, hospital and run we think it is, and a first try.
def load_saved(path, patient_id, hospital, run_id):
    saved = json.loads(path.read_text(encoding="utf-8"))
    if saved["patient_id"] != patient_id or saved["hospital"] != hospital:
        raise ValueError(f"{path.name} does not match {patient_id}, hospital {hospital}")
    if saved.get("run_id", run_id) != run_id:
        raise ValueError(f"{path.name} belongs to another run, not {run_id}")
    if saved.get("attempt", 1) != 1:
        raise ValueError(f"{path.name} is not a first try (attempt {saved['attempt']})")
    return saved


# Stack one patient's three saved files into one compiled-shape record.
def build_row_record(source_root, run_id, patient_id):
    extractions = []
    for hospital, path in zip(HOSPITALS, saved_paths(source_root, run_id, patient_id)):
        saved = load_saved(path, patient_id, hospital, run_id)
        extractions.append({
            "patient_id": patient_id,
            "hospital": hospital,
            "source_file": saved["source_file"],
            "facts": saved["facts"],
        })
    return build_record(KIND, patient_id, run_id, extractions)


# Build and write every patient's record. Stops first, writing nothing, if any file is missing.
# Returns (patients written, facts written).
def run_row(source_root, run_id, ids, out_dir, hidden):
    missing = find_missing(source_root, run_id, ids)
    if missing:
        files = sum(len(names) for names in missing.values())
        detail = "" if hidden else " " + "; ".join(f"{pid}: {', '.join(names)}" for pid, names in missing.items())
        raise SystemExit(f"STOP: {len(missing)} of {len(ids)} patients are missing saved files "
                         f"({files} files missing) in {Path(source_root) / run_id}. Nothing written.{detail}")
    total_facts = 0
    for pid in ids:
        record = build_row_record(source_root, run_id, pid)
        out = Path(out_dir) / f"{pid}.json"
        write_record(record, out)
        heldout_guard.say(pid, len(record["facts"]), out, hidden)
        total_facts += len(record["facts"])
    return len(ids), total_facts


def main():
    ap = argparse.ArgumentParser(description="Build-up rows 4-6 (T65): stack saved extractions. No model calls.")
    ap.add_argument("patients", nargs="*", help="e.g. D001 P001")
    ap.add_argument("--row", type=int, choices=sorted(ROW_SOURCE), required=True,
                    help="4 plain lists, 5 labels (first tries), 6 labels + check")
    ap.add_argument("--run-id", required=True, help="e.g. 20261115-v2-sonnet-5-5")
    ap.add_argument("--working", action="store_true", help="run P001 to P020")
    ap.add_argument("--source-root", default=None,
                    help="folder holding the run folders (default outputs/extracted for rows 4-5, outputs/checked for row 6)")
    ap.add_argument("--out-dir", default=None,
                    help="where to write (required for working and demo; held-out default "
                         "outputs/results_heldout/row<N>)")
    heldout_guard.add_heldout_args(ap)
    args = ap.parse_args()

    ids = list(args.patients) + (heldout_guard.WORKING if args.working else [])
    if not ids and not args.all_heldout:
        ap.error("give patient IDs, or --working, or --all-heldout")
    ids = list(dict.fromkeys(heldout_guard.pick_ids(ap, args, ids)))  # keep order, drop repeats

    any_heldout = any(heldout_guard.is_heldout_id(pid) for pid in ids)
    if not args.out_dir and not any_heldout:
        ap.error("give --out-dir (working output goes to a scratch folder outside the repo)")
    out_dir = heldout_guard.pick_out_dir(args.out_dir, ids, "", f"row{args.row}")

    # Held-out guard: the freeze tag and a git-ignored folder, checked before any saved file is opened.
    hidden = heldout_guard.guard_run(ids, [out_dir / f"{pid}.json" for pid in ids])

    source_root = Path(args.source_root) if args.source_root else ROW_SOURCE[args.row]
    patients, facts = run_row(source_root, args.run_id, ids, out_dir, hidden)
    print(f"Row {args.row}: {patients} patients, {facts} facts -> {out_dir}")


if __name__ == "__main__":
    main()
