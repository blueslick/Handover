"""Held-out guard for the eval scripts (T65): one place for the rules about held-out patients.

The baselines, the omission check, the build-up runner and score.py all use these checks, so
the rules are written once. Held-out means the 160 patients that pipeline/data/patients.csv marks with split "heldout"
(80) or "reserve" (80); record_format.md calls that file the source of truth for the split.
(The .txt files in pipeline/data/split/ hold Synthea IDs, not patient IDs.) The demo patient
and the 20 working patients are open as always.

Before a script opens any held-out file it must pass require_heldout_ok():
  (a) the `freeze` tag exists (the same check as pipeline/tool/run_records.py), and
  (b) every file it will write sits in a git-ignored folder (the same check as score.py).
If either fails the script stops, and nothing held-out has been opened. Held-out output goes
under outputs/results_heldout/, which .gitignore lists, so it can never be committed.

This file only reads patients.csv, for the patient IDs and their split. It never opens a patient
record and makes no model calls.
"""

import csv
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "pipeline" / "data"
PATIENTS_CSV = DATA / "patients.csv"
# Held-out output goes here by default. .gitignore lists this folder.
RESULTS_HELDOUT = REPO / "outputs" / "results_heldout"

DEMO_ID = "D001"
WORKING = [f"P{n:03d}" for n in range(1, 21)]
# The only IDs the scripts accept without --heldout.
OPEN_IDS = [DEMO_ID] + WORKING


# The 160 held-out patient IDs: every patients.csv row whose split is "heldout" or "reserve".
def heldout_ids():
    with PATIENTS_CSV.open(encoding="utf-8", newline="") as handle:
        return [row["patient_id"] for row in csv.DictReader(handle)
                if row["split"] in ("heldout", "reserve")]


# Anything that is not the demo patient or a working patient counts as held-out.
def is_heldout_id(patient_id):
    return patient_id not in OPEN_IDS


# The folder that holds one patient's three hospital records (folders_and_names.md).
def patient_folder(patient_id):
    if patient_id.startswith("D"):
        return DATA / "demo" / patient_id
    if patient_id.startswith("R"):
        return DATA / "reserve" / patient_id
    return DATA / ("working" if patient_id in WORKING else "heldout") / patient_id


# Is there a `freeze` git tag? Same one-line check as run_records.freeze_tag_exists().
def freeze_tag_exists():
    out = subprocess.run(["git", "-C", str(REPO), "tag", "-l", "freeze"],
                         capture_output=True, text=True, encoding="utf-8")
    return out.stdout.strip() == "freeze"


# Stop unless the freeze tag exists.
def require_freeze_tag():
    if not freeze_tag_exists():
        raise SystemExit("STOP: there is no `freeze` tag yet, so held-out patients can't be used "
                         "(CLAUDE.md, Held-out patients).")


# Ask git whether a path is ignored. If git cannot answer (not a repo, or the path is outside
# the repo) this returns False, so the check fails closed. Same logic as score._is_git_ignored().
def is_git_ignored(path):
    try:
        result = subprocess.run(["git", "check-ignore", "-q", "--", str(Path(path).resolve())],
                                cwd=REPO, capture_output=True)
    except OSError:
        return False
    return result.returncode == 0


# Stop unless every file about to be written is git-ignored. The message names the folder only.
def require_ignored(paths):
    for path in paths:
        if not is_git_ignored(path):
            folder = Path(path).resolve().parent
            raise SystemExit(f"STOP: held-out output must go to a git-ignored folder, but {folder} is not "
                             "ignored by git. Use a folder under outputs/results_heldout/.")


# The full guard. Call it before opening any held-out file.
def require_heldout_ok(output_paths):
    require_freeze_tag()
    require_ignored(output_paths)


# Add --heldout and --all-heldout to a script's command line.
def add_heldout_args(ap):
    ap.add_argument("--heldout", action="store_true",
                    help="allow held-out and reserve patients (after the freeze only; output must be git-ignored)")
    ap.add_argument("--all-heldout", action="store_true",
                    help="all 160 held-out patients (needs --heldout)")


# Work out the final ID list and refuse anything not allowed. Without --heldout only the demo
# and working patients pass, with the same message the scripts always gave.
def pick_ids(ap, args, ids):
    if args.all_heldout and not args.heldout:
        ap.error("--all-heldout needs --heldout")
    ids = list(ids)
    allowed = set(OPEN_IDS)
    if args.heldout:
        held = heldout_ids()
        allowed.update(held)
        if args.all_heldout:
            ids.extend(held)
    for pid in ids:
        if pid not in allowed:
            if args.heldout:
                ap.error(f"{pid} is not a demo, working or held-out patient ID")
            ap.error(f"{pid} is not allowed: only D001 and P001-P020 (held-out and reserve IDs are refused)")
    return ids


# Where to write. An explicit --out-dir always wins (and is still guarded for held-out).
# Otherwise any held-out ID sends the output to outputs/results_heldout/<heldout_name>.
def pick_out_dir(out_dir_arg, ids, normal_default, heldout_name):
    if out_dir_arg:
        return Path(out_dir_arg)
    if any(is_heldout_id(pid) for pid in ids):
        return RESULTS_HELDOUT / heldout_name
    return Path(normal_default)


# Run the guard for a script. Returns True when any held-out patient is in this run.
# Only the held-out case is checked: a run on working patients is left exactly as it was.
def guard_run(ids, output_paths):
    if not any(is_heldout_id(pid) for pid in ids):
        return False
    require_heldout_ok(output_paths)
    return True


# For held-out runs, stop early if any patient lacks its 3 records. Reports a count, never an ID.
def require_three_records(ids, record_files):
    short = sum(1 for pid in ids if len(record_files(pid)) != 3)
    if short:
        raise SystemExit(f"STOP: {short} of {len(ids)} patients do not have exactly 3 hospital records. "
                         "Nothing was written.")


# Print one line per patient for the normal case. For held-out runs print nothing here
# (the script prints one summary of counts at the end), so no ID or content reaches the screen.
def say(patient_id, n_facts, out, hidden):
    if not hidden:
        print(f"{patient_id}: {n_facts} facts -> {out}")
