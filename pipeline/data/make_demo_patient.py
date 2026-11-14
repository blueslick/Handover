"""Build the demo patient D001 (T05): three hospital records and the answer key.

The demo patient is made up, not taken from Synthea, and is never scored (CLAUDE.md).
It carries the whole demo video, so it plants exactly the cases the plan asks for:

    1. A penicillin allergy that only Hospital A recorded. Hospitals B and C say
       "no known allergies", so the key shows a conflict (compile rule 5).
    2. Warfarin current at Hospital A, then stopped in Hospital B's letter (rule 2).
       Hospital C doesn't mention it, and silence is not a stop (rule 4).
    3. Metformin 500 mg at Hospital A, then 1000 mg at B and C (rule 3, dose changed).
       Hospital C writes it as "Glucophage 1 g BD": brand name and grams.
    4. Paracetamol written as "Panadol 1 g PRN" in Hospital C only (brand to generic).

The records are written by the T12 templates (code, not an AI), and the key by the
T14 answer-key script, so the demo goes through exactly the same code as every patient.

Usage:
    python pipeline/data/make_demo_patient.py           writes the 5 files into pipeline/data/demo/D001/
    python pipeline/data/make_demo_patient.py --print   also prints the three records
"""
import argparse
import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent
sys.path.insert(0, str(DATA / "templates"))
sys.path.insert(0, str(DATA))

from make_records import FILE_ENDINGS, render          # noqa: E402  (T12 templates)
from make_answer_key import write_key                   # noqa: E402  (T14 answer key)

OUT = DATA / "demo" / "D001"

# Who the patient is. The name is made up.
PATIENT = {"patient_id": "D001", "first_name": "Nora", "last_name": "Hashim",
           "birth_date": "1958-03-22", "sex": "F"}

# The medicine rows used, exactly as they are named in templates/medicine_table.csv.
METFORMIN_500 = "DEMO Metformin 500 MG Oral Tablet"
METFORMIN_1000 = "DEMO Metformin 1000 MG Oral Tablet"
PARACETAMOL_1G = "DEMO Paracetamol 1000 MG Oral Tablet"
WARFARIN_5 = "Warfarin Sodium 5 MG Oral Tablet"

DIABETES = {"description": "Type 2 diabetes", "start": "2017-04-03"}
AF = {"description": "Atrial fibrillation", "start": "2019-05-02"}

# What each hospital knows on its visit date. This is the "placement" for the demo
# patient: which facts each hospital gets, and when.
VISITS = [
    # Hospital A, March 2021: the only record of the penicillin allergy.
    # Warfarin and metformin 500 mg both current.
    dict(PATIENT, hospital="A", visit_date="2021-03-02",
         allergies=[{"synthea_name": "Penicillin V", "reactions": ["Eruption of skin (disorder)"],
                     "start": "2009-08-14"}],
         diagnoses=[DIABETES, AF],
         medicines=[{"synthea_description": METFORMIN_500, "status": "current", "date": "2017-04-10"},
                    {"synthea_description": WARFARIN_5, "status": "current", "date": "2019-05-10"}]),

    # Hospital B, July 2021: no known allergies, warfarin stopped, metformin now 1000 mg.
    dict(PATIENT, hospital="B", visit_date="2021-07-14",
         allergies=[],
         diagnoses=[DIABETES, AF],
         medicines=[{"synthea_description": METFORMIN_1000, "status": "current", "date": "2021-07-14"},
                    {"synthea_description": WARFARIN_5, "status": "stopped", "date": "2021-06-20"}]),

    # Hospital C, October 2021: brand names. Metformin 1000 mg as Glucophage 1 g,
    # paracetamol as Panadol 1 g. Says nothing about warfarin.
    dict(PATIENT, hospital="C", visit_date="2021-10-05",
         allergies=[],
         diagnoses=[DIABETES],
         medicines=[{"synthea_description": METFORMIN_1000, "status": "current", "date": "2021-10-05"},
                    {"synthea_description": PARACETAMOL_1G, "status": "current", "date": "2021-10-05"}]),
]

# The patient's whole history in the same shape the trim script gives working patients,
# so the folder has the usual five files and `make_records.py --check-tables` covers it.
SUMMARY = {
    "patient_id": "D001",
    "synthea_id": None,
    "source": "Made up for the demo video (T05). Not from Synthea. Never scored.",
    "sex": PATIENT["sex"], "birth_date": PATIENT["birth_date"], "age_on_reference_date": 63,
    "age_band": "45-64", "first_name": PATIENT["first_name"], "last_name": PATIENT["last_name"],
    "window": {"reference_date": "2021-11-18", "window_start": "2016-11-18"},
    "allergies": [{"name": "Penicillin V", "category": "medication",
                   "reactions": [{"reaction": "Eruption of skin (disorder)", "severity": "MILD"}],
                   "start": "2009-08-14", "active": True}],
    "diagnoses": [dict(DIABETES, code=None), dict(AF, code=None)],
    "current_medicines": [
        {"description": METFORMIN_1000, "code": None, "start": "2021-07-14", "reason": "Type 2 diabetes"},
        {"description": PARACETAMOL_1G, "code": None, "start": "2021-10-05", "reason": None}],
    "stopped_medicines": [{"description": WARFARIN_5, "code": None, "last_stop": "2021-06-20"}],
    "dose_changes": [{"name": "Metformin",
                      "current": {"description": METFORMIN_1000, "strength": "1000 MG"},
                      "stopped": {"description": METFORMIN_500, "strength": "500 MG",
                                  "last_stop": "2021-07-14"}}],
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--print", action="store_true", help="also print the three records")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    # Write the three hospital records with the T12 templates, and keep what each one wrote.
    records = []
    for visit in VISITS:
        text, facts = render(visit)
        name = "D001" + FILE_ENDINGS[visit["hospital"]]
        (OUT / name).write_text(text, encoding="utf-8")
        records.append({"hospital": visit["hospital"], "file": name, "facts": facts})
        if args.print:
            print(f"----- {name} -----\n{text}")

    # The history summary, so the folder matches every other patient folder.
    (OUT / "D001_synthea.json").write_text(json.dumps(SUMMARY, indent=2) + "\n", encoding="utf-8")

    # The answer key, built by the T14 script (it checks every quote against the files above
    # and validates the result with shared/validate.py).
    out, n_facts, n_conflicts, warnings = write_key("D001", records)
    print(f"OK   D001: 3 records, key with {n_facts} facts and {n_conflicts} conflict group(s) -> {out.relative_to(DATA.parent.parent)}")
    for w in warnings:
        print("     ", w)


if __name__ == "__main__":
    main()
