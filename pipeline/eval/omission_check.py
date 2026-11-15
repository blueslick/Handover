"""Omission check (T41): flag names in a hospital record that the saved extraction left out.

For one hospital record, every drug name, brand name (turned into its generic name) and
allergy word in the source text is looked up. If the record's saved extraction has no fact
with the same generic name, that name gets a possible_missed flag, with the line it came from.

The check only reads files and makes no model calls. It never changes a saved extraction.
Its flags go to a separate file per record: outputs/omission/<run_id>/<PID>_<H>.json.

Usage (from the repo root, with the project venv):
    .venv/bin/python pipeline/eval/omission_check.py --run-id 20261114-v1-sonnet-5-5 D001

Only D001 and P001 to P020 are allowed. Held-out and reserve IDs are refused before any
file is opened. The name lists and the matching rules come from keyword_baseline.py (T24),
so the baseline and this check use the same definitions.
"""

import argparse
import json
from pathlib import Path

import keyword_baseline as kb

REPO = Path(__file__).resolve().parents[2]
EXTRACTED = REPO / "outputs" / "extracted"
OMISSION = REPO / "outputs" / "omission"

# The flag name is read from the team's fixed list, so it is spelled exactly as there.
FIXED = json.loads((REPO / "shared" / "fixed_lists.json").read_text(encoding="utf-8"))
FLAG = "possible_missed"
if FLAG not in FIXED["flags"]:
    raise RuntimeError("possible_missed is not in shared/fixed_lists.json")


# Refuse any patient ID that is not D001 or P001 to P020. This runs before any file is opened.
def check_allowed(patient_id):
    if patient_id not in kb.ALLOWED:
        raise ValueError(
            f"{patient_id} is not allowed: only D001 and P001-P020 "
            "(held-out and reserve IDs are refused)"
        )


# Find every name in one line of source text. Returns (text as written, generic name) pairs in order.
def names_in_line(line, names, pattern):
    return [(m.group(0), names[m.group(0).lower()]) for m in pattern.finditer(line)]


# Compare one source record with its saved extraction and return the possible_missed flags.
# A name is flagged when no extracted fact has the same generic name, whatever the fact's type.
# Each generic name gets one flag, listing every line that mentions it.
def check_record(source_text, facts, names, pattern):
    extracted = {f["name"].strip().lower() for f in facts if f.get("name")}
    by_generic = {}
    for line_no, raw in enumerate(source_text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        for written, generic in names_in_line(line, names, pattern):
            if generic in extracted:
                continue
            flag = by_generic.setdefault(
                generic,
                {"flag": FLAG, "generic": generic, "terms_as_written": [], "lines": []},
            )
            if written not in flag["terms_as_written"]:
                flag["terms_as_written"].append(written)
            flag["lines"].append({"line": line_no, "text": line})
    return list(by_generic.values())


# Check every hospital record for one patient. A record with no saved extraction is skipped and
# reported as skipped. It is never guessed at, because that would flag every name in it.
def run_patient(patient_id, run_id, extracted_root, out_root, names, pattern):
    check_allowed(patient_id)
    results = []
    for path in kb.record_files(patient_id):
        hospital = path.stem.split("_")[-1]
        extraction = Path(extracted_root) / run_id / f"{patient_id}_{hospital}.json"
        if not extraction.exists():
            results.append({"hospital": hospital, "status": "skipped: no saved extraction", "written": None})
            continue
        # Make sure the saved file really is this patient, hospital and run before using it.
        saved = json.loads(extraction.read_text(encoding="utf-8"))
        if saved["patient_id"] != patient_id or saved["hospital"] != hospital or saved["run_id"] != run_id:
            raise ValueError(f"{extraction.name} does not match {patient_id}, hospital {hospital}, run {run_id}")
        source_text = path.read_text(encoding="utf-8")
        flags = check_record(source_text, saved["facts"], names, pattern)
        out = {
            "kind": "omission_check",
            "patient_id": patient_id,
            "hospital": hospital,
            "run_id": run_id,
            "source_file": path.name,
            "extraction_file": extraction.name,
            "flags": flags,
        }
        # Write the flags to their own file. The saved extraction is only read, never written.
        out_file = Path(out_root) / run_id / f"{patient_id}_{hospital}.json"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        results.append({"hospital": hospital, "status": f"{len(flags)} possible_missed", "written": out_file})
    return results


# Command line entry point: check the named patients against one extraction run.
def main():
    ap = argparse.ArgumentParser(description="Omission check (T41). See the top of this file.")
    ap.add_argument("patients", nargs="+", help="e.g. D001 P001")
    ap.add_argument("--run-id", required=True, help="the extraction run to check, e.g. 20261114-v1-sonnet-5-5")
    ap.add_argument("--extracted-root", default=str(EXTRACTED), help="default outputs/extracted")
    ap.add_argument("--out-root", default=str(OMISSION), help="default outputs/omission")
    args = ap.parse_args()

    for pid in args.patients:
        if pid not in kb.ALLOWED:
            ap.error(f"{pid} is not allowed: only D001 and P001-P020 (held-out and reserve IDs are refused)")

    names = kb.load_names()
    pattern = kb.build_pattern(names)
    for pid in dict.fromkeys(args.patients):
        for result in run_patient(pid, args.run_id, args.extracted_root, args.out_root, names, pattern):
            where = f" -> {result['written']}" if result["written"] else ""
            print(f"{pid} hospital {result['hospital']}: {result['status']}{where}")


if __name__ == "__main__":
    main()
