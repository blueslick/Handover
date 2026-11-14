"""Store step (pipeline section 8, T25): keep compiled records as JSON, one fact per entry.

The per-patient files (P014.json) are the store. This script only rebuilds the two
files made from them, and copies one run into outputs/published/ for the app.
Spec: shared/store_layout.md.

Usage:
    python pipeline/tool/store.py build outputs/compiled/<run_id>
    python pipeline/tool/store.py build outputs/baseline_keyword
    python pipeline/tool/store.py publish --run <run_id> [--patients D001 P021 ...] [--results <run_id>]

Prints counts only, never facts, so it is safe on held-out output.
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
from validate import check_file  # noqa: E402

PATIENT_FILE = re.compile(r"^[PRD]\d{3}\.json$")
CRITICAL_TYPES = {"allergy", "medicine"}
WARNING_FLAGS = {"unverified", "conflict", "missing_dose"}


class StoreError(Exception):
    pass


def patient_files(folder):
    """The per-patient record files in a folder, sorted by patient ID."""
    if not Path(folder).is_dir():
        raise StoreError(f"no such folder: {folder}")
    return sorted(p for p in Path(folder).iterdir() if PATIENT_FILE.match(p.name))


def counts(record):
    """The numbers the index shows for one patient."""
    facts = record["facts"]
    critical = [f for f in facts if f["type"] in CRITICAL_TYPES]
    return {
        "facts": len(facts),
        "critical_facts": len(critical),
        "critical_warnings": sum(1 for f in critical if WARNING_FLAGS & set(f["flags"])),
        "conflicts": len({f["conflict_group"] for f in facts if f["conflict_group"]}),
    }


def load_checked(folder):
    """Read every patient file, after running all checks. Raises StoreError on any problem."""
    files = patient_files(folder)
    if not files:
        raise StoreError(f"no patient files (P014.json style) in {folder}")
    records, problems = [], []
    for path in files:
        errs = check_file(path, "compiled")
        if errs:
            problems.append(f"{path.name}: fails shared/validate.py ({len(errs)} problems)")
            continue
        rec = json.loads(path.read_text(encoding="utf-8"))
        if path.stem != rec["patient_id"]:
            problems.append(f"{path.name}: holds patient {rec['patient_id']}")
        records.append((path, rec))
    kinds = {(r["kind"], r["run_id"]) for _, r in records}
    if len(kinds) > 1:
        problems.append(f"files disagree on kind/run_id: {sorted(kinds, key=str)}")
    if problems:
        raise StoreError("nothing written:\n  " + "\n  ".join(problems))
    return records


def build(folder):
    """Write facts.jsonl and index.json beside the patient files. Returns the index."""
    folder = Path(folder)
    records = load_checked(folder)
    kind, run_id = records[0][1]["kind"], records[0][1]["run_id"]
    lines, patients = [], []
    for path, rec in records:
        for fact in rec["facts"]:
            lines.append(json.dumps({"run_id": run_id, "kind": kind, **fact}, ensure_ascii=False))
        patients.append({"patient_id": rec["patient_id"], "file": path.name, **counts(rec)})
    index = {"format_version": "1.0", "kind": kind, "run_id": run_id, "patients": patients}
    (folder / "facts.jsonl").write_text("".join(l + "\n" for l in lines), encoding="utf-8")
    (folder / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return index


def publish(run_id, outputs, patients=None, results=None):
    """Copy one compiled run (and matching keyword baselines) into outputs/published/."""
    outputs = Path(outputs)
    run_dir = outputs / "compiled" / run_id
    if not run_dir.is_dir():
        raise StoreError(f"no such run folder: {run_dir}")
    records = load_checked(run_dir)
    if records[0][1]["kind"] != "compiled":
        raise StoreError(f"{run_dir} holds kind {records[0][1]['kind']}, not compiled")
    by_id = {rec["patient_id"]: (path, rec) for path, rec in records}
    wanted = patients or sorted(by_id)
    missing = [p for p in wanted if p not in by_id]
    if missing:
        raise StoreError(f"not in run {run_id}: {', '.join(missing)}")

    baseline_dir = outputs / "baseline_keyword"
    baselines = {}
    if baseline_dir.is_dir() and patient_files(baseline_dir):
        baselines = {rec["patient_id"]: path for path, rec in load_checked(baseline_dir)}

    pub = outputs / "published"
    for sub in ("compiled", "baseline_keyword"):
        (pub / sub).mkdir(parents=True, exist_ok=True)
        for old in patient_files(pub / sub):
            old.unlink()
    entries = []
    for pid in wanted:
        path, rec = by_id[pid]
        shutil.copyfile(path, pub / "compiled" / path.name)
        has_baseline = pid in baselines
        if has_baseline:
            shutil.copyfile(baselines[pid], pub / "baseline_keyword" / f"{pid}.json")
        entries.append({"patient_id": pid, "has_baseline": has_baseline, **counts(rec)})
    if results:
        src = outputs / "results" / results
        if not src.is_dir():
            raise StoreError(f"no such results folder: {src}")
        shutil.copytree(src, pub / "results", dirs_exist_ok=True)
    index = {"format_version": "1.0", "compiled_run_id": run_id, "patients": entries}
    (pub / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return index


def summary(index):
    pts = index["patients"]
    return (f"{len(pts)} patients, {sum(p['facts'] for p in pts)} facts, "
            f"{sum(p['critical_warnings'] for p in pts)} critical warnings, "
            f"{sum(p['conflicts'] for p in pts)} conflicts")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="rebuild facts.jsonl and index.json in a folder")
    b.add_argument("folder")
    p = sub.add_parser("publish", help="copy one compiled run into outputs/published/")
    p.add_argument("--run", required=True)
    p.add_argument("--patients", nargs="+")
    p.add_argument("--results", help="results run ID to copy into published/results/")
    p.add_argument("--outputs", default=str(ROOT / "outputs"), help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    try:
        if args.cmd == "build":
            print(f"built {args.folder}: {summary(build(args.folder))}")
        else:
            index = publish(args.run, args.outputs, args.patients, args.results)
            print(f"published run {args.run}: {summary(index)}")
    except StoreError as e:
        print(f"store.py: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
