"""Score several methods on allergies and medicines only (T76), with score.py unchanged.

The Azure baseline (T76) only produces allergies and medicines, so it is compared with the other
methods on that subset only. For each method this script:
1. copies each patient's compiled record and answer key, keeping only facts of type allergy or
   medicine on BOTH sides (the same type filter as score_single_notes.py, T43), and
2. runs score.py's own main() on those copies. Matching and counting are score.py's, untouched.
Then it writes one line per method and scope (all facts / critical facts) into lines.csv.

Usage (from the repo root, with the project venv):
    .venv/bin/python pipeline/eval/score_am_subset.py --out-root outputs/results/t76_am_subset \
        --method keyword=outputs/baseline_keyword --method azure=outputs/baseline_azure --working

Held-out (after the freeze only): add --heldout --all-heldout. The output root must be git-ignored
(outputs/results_heldout/...); score.py checks that and the freeze tag itself. The filtered copies
go inside the output root. --totals-csv FILE also writes the totals (no patient IDs, no quotes)
to FILE, which can then be committed; the script refuses to write anything shaped like a patient ID
there. It reads files only and makes no model or Azure calls.
"""

import argparse
import csv
import json
import re
import sys
import tempfile
from pathlib import Path

import heldout_guard
import score

KEEP_TYPES = ("allergy", "medicine")
ID_SHAPE = re.compile(r"\b[PRD]\d{3}\b")
LINE_FIELDS = ["method", "scope", "patients"] + score.COUNT_FIELDS + ["recall", "precision"]


# Keep only allergy and medicine facts. Nothing else in the record changes.
def filtered(record):
    out = dict(record)
    out["facts"] = [f for f in record["facts"] if f["type"] in KEEP_TYPES]
    return out


def write_json(record, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


# Write the filtered copies of every answer key once, into keys_dir/<ID>_key.json.
def copy_keys(ids, keys_dir):
    for pid in ids:
        key = score.load_json(heldout_guard.patient_folder(pid) / f"{pid}_key.json")
        write_json(filtered(key), keys_dir / f"{pid}_key.json")


# Score one method on the subset with score.py's main(), and return its two summary rows.
def score_method(name, compiled_dir, ids, keys_dir, inputs, out_dir, include_heldout):
    method_inputs = inputs / name
    for pid in ids:
        write_json(filtered(score.load_json(Path(compiled_dir) / f"{pid}.json")), method_inputs / f"{pid}.json")
    argv = ["--compiled-dir", str(method_inputs), "--keys-dir", str(keys_dir),
            "--out-dir", str(out_dir), "--patients", *ids]
    if include_heldout:
        argv.append("--include-heldout")
    # score.py prints patient IDs; keep its screen output for working runs only.
    if include_heldout:
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            score.main(argv)
    else:
        score.main(argv)
    with (out_dir / "summary.csv").open(encoding="utf-8", newline="") as handle:
        return [{"method": name, **row} for row in csv.DictReader(handle)]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Score methods on allergies and medicines only (T76).")
    ap.add_argument("--out-root", type=Path, required=True)
    ap.add_argument("--method", action="append", required=True, metavar="NAME=COMPILED_DIR")
    ap.add_argument("patients", nargs="*")
    ap.add_argument("--working", action="store_true", help="P001 to P020")
    ap.add_argument("--totals-csv", type=Path, default=None, help="also write totals only (no IDs) here")
    heldout_guard.add_heldout_args(ap)
    args = ap.parse_args(argv)

    ids = list(args.patients) + (heldout_guard.WORKING if args.working else [])
    ids = list(dict.fromkeys(heldout_guard.pick_ids(ap, args, ids)))
    if not ids:
        ap.error("give patient IDs, or --working, or --heldout --all-heldout")
    hidden = any(heldout_guard.is_heldout_id(p) for p in ids)
    methods = [m.split("=", 1) for m in args.method]

    # Held-out: freeze tag and a git-ignored output root, checked before any held-out file is opened.
    if hidden:
        heldout_guard.require_heldout_ok([args.out_root / "lines.csv", args.out_root / "_inputs" / "x.json"])

    # Filtered copies: inside the git-ignored root for held-out, in a temporary folder otherwise.
    temp = None
    if hidden:
        inputs = args.out_root / "_inputs"
    else:
        temp = tempfile.TemporaryDirectory()
        inputs = Path(temp.name)
    try:
        keys_dir = inputs / "_keys"
        copy_keys(ids, keys_dir)
        lines = []
        for name, compiled_dir in methods:
            lines += score_method(name, compiled_dir, ids, keys_dir, inputs, args.out_root / name, hidden)
    finally:
        if temp is not None:
            temp.cleanup()

    args.out_root.mkdir(parents=True, exist_ok=True)
    score._write_csv(args.out_root / "lines.csv", LINE_FIELDS, lines)
    if args.totals_csv:
        buffer = "\n".join(",".join(str(row[f]) for f in LINE_FIELDS) for row in lines)
        if ID_SHAPE.search(buffer):
            raise SystemExit("STOP: the totals contain something shaped like a patient ID. Nothing was written.")
        args.totals_csv.parent.mkdir(parents=True, exist_ok=True)
        score._write_csv(args.totals_csv, LINE_FIELDS, lines)
    for row in lines:
        print(f"{row['method']:>14} {row['scope']:>8}: key {row['key_facts']}, matched {row['matched']}, "
              f"missed {row['missed']}, false alarms {row['false_alarms']} "
              f"(duplicates {row['duplicates']}), wrong status {row['wrong_status']}, "
              f"conflicts {row['conflict_shown']}/{row['conflict_facts']}, "
              f"recall {row['recall']}, precision {row['precision']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
