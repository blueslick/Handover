"""Stack-everything merge (T24): keep every fact from every hospital, each as its own entry.

This file does not know how the facts were found. It takes facts in the extracted
shape (shared/schema/extracted.schema.json, one file per hospital record) and returns
compiled facts (shared/schema/compiled.schema.json). So the same merge can later run on
Claude's saved extractions as well as on the keyword output.

There is no deduplication, no stop logic and no conflict flags. That is the point of
this baseline: it shows what happens when nothing is merged.
"""

import json
from pathlib import Path

FORMAT_VERSION = "1.0"


# Stack every fact from one patient's hospital records into one flat list.
def stack_merge(patient_id, extractions):
    # Refuse any record that belongs to a different patient, so a mix-up cannot pass silently.
    for ext in extractions:
        if ext["patient_id"] != patient_id:
            raise ValueError(f"{ext['source_file']} belongs to {ext['patient_id']}, not {patient_id}")

    # Keep hospitals in A, B, C order, so the output does not depend on the order the files came in.
    ordered = sorted(extractions, key=lambda ext: ext["hospital"])

    compiled = []
    for ext in ordered:
        for fact in ext["facts"]:
            number = len(compiled) + 1
            compiled.append({
                "fact_id": f"{patient_id}-F{number:02d}",
                "patient_id": patient_id,
                "type": fact["type"],
                "name": fact["name"],
                "name_as_written": fact["name_as_written"],
                "dose": fact["dose"],
                "frequency": fact["frequency"],
                "reaction": fact["reaction"],
                "status": fact["status"],
                "hospital": ext["hospital"],
                "date": fact["date"],
                "quote": fact["quote"],
                # Each entry has exactly one source: the record it came from.
                "sources": [{
                    "hospital": ext["hospital"],
                    "date": fact["date"],
                    "quote": fact["quote"],
                    "file": ext["source_file"],
                }],
                "history": [],
                "flags": list(fact["flags"]),
                "conflict_group": None,
            })
    return compiled


# Wrap the stacked facts in the compiled file shape (compiled.schema.json).
def build_record(kind, patient_id, run_id, extractions):
    ordered = sorted(extractions, key=lambda ext: ext["hospital"])
    return {
        "format_version": FORMAT_VERSION,
        "kind": kind,
        "patient_id": patient_id,
        "run_id": run_id,
        "built_from": [ext["source_file"] for ext in ordered],
        "facts": stack_merge(patient_id, extractions),
    }


# Write one compiled record as UTF-8 JSON, creating the folder if needed.
def write_record(record, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
