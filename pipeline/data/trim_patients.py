"""Trim each patient's Synthea history to the 5 years before the reference date (T11).

Reads the raw Synthea CSVs in pipeline/data/synthea_raw/csv/ (git-ignored, see
pipeline/data/README.md) and the split in pipeline/data/patients.csv. Writes one JSON
file per working, held-out and reserve patient, for example:

    pipeline/data/working/P001/P001_synthea.json
    pipeline/data/heldout/P021/P021_synthea.json
    pipeline/data/reserve/R001/R001_synthea.json

Reserve patients (R001-R080) were added to the held-out set by T59 and are trimmed too.

Run from the repo root:

    python pipeline/data/trim_patients.py           # all 180 patients
    python pipeline/data/trim_patients.py --test    # only P001 and P002 (working)

For held-out and reserve patients only totals are printed. Their contents are never printed.
"""

import argparse
import csv
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

# Where things live. Paths are built from this script's own folder, so no absolute paths are written.
DATA_DIR = Path(__file__).resolve().parent
RAW_CSV_DIR = DATA_DIR / "synthea_raw" / "csv"
SPLIT_FILE = DATA_DIR / "patients.csv"
OUT_DIRS = {"working": DATA_DIR / "working", "heldout": DATA_DIR / "heldout", "reserve": DATA_DIR / "reserve"}
TEST_PATIENTS = ("P001", "P002")

# The reference date is the last date in the sample. The window is the 5 years before it.
REFERENCE_DATE = date(2021, 11, 18)
WINDOW_START = REFERENCE_DATE.replace(year=REFERENCE_DATE.year - 5)

# A number followed by an upper-case unit, e.g. "500 MG", "100 UNT/ML", "50 %".
# The \b stops it matching inside names such as "B12".
STRENGTH = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|[A-Z]+(?:/[A-Z]+)?)(?![A-Za-z])")
# Trailing digits on a name, e.g. "Asia282" -> "Asia".
TRAILING_DIGITS = re.compile(r"\d+$")

# Diagnoses dropped from the active list: social notes and similar suffixes, and past illnesses.
DIAGNOSIS_EXCLUDED_SUFFIXES = ("(finding)", "(person)", "(situation)")
DIAGNOSIS_EXCLUDED_PREFIX = "History of"


def to_date(text, where):
    # Turn a Synthea timestamp such as 2014-08-11T15:24:50Z into a date. A blank cell gives None.
    # The error message names the column only, never the value, so no patient data is printed.
    if not text or not text.strip():
        return None
    try:
        return date.fromisoformat(text.strip()[:10])
    except ValueError:
        raise ValueError(f"Unreadable date in {where}") from None


def iso(day):
    # Plain YYYY-MM-DD for the output, or None for a missing date.
    return day.isoformat() if day else None


def in_window(day):
    # True if the date falls inside the 5-year window (both ends included).
    return day is not None and WINDOW_START <= day <= REFERENCE_DATE


def age_on(birth, on):
    # Whole years from the birth date to the given date.
    return on.year - birth.year - ((on.month, on.day) < (birth.month, birth.day))


def age_band_for(age):
    # The same four bands used in the split (computed on 18 Nov 2021).
    if age < 20:
        return "0-19"
    if age < 45:
        return "20-44"
    if age < 65:
        return "45-64"
    return "65+"


def split_medicine(description):
    # Split a medicine description into its name and its strength.
    # The name is the text before the first strength; the strength is every number-with-unit in the text.
    # Example: "Metformin 500 MG Oral Tablet" -> ("Metformin", "500 MG").
    found = STRENGTH.findall(description)
    if not found:
        return description.strip(), ""
    first = STRENGTH.search(description)
    name = description[: first.start()].strip()
    strength = " / ".join(" ".join(item.split()) for item in found)
    return name, strength


def read_split():
    # Read pipeline/data/patients.csv. Keep the working, held-out and reserve rows (reserve added to held-out by T59).
    with SPLIT_FILE.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [row for row in rows if row["split"] in OUT_DIRS]


def read_raw_rows(file_name, wanted_ids, id_column):
    # Read one raw Synthea CSV as UTF-8 and keep only the rows for the patients we need.
    # Returns a dict: Synthea patient ID -> list of rows, in file order.
    rows_by_id = {}
    with (RAW_CSV_DIR / file_name).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = row[id_column]
            if key in wanted_ids:
                rows_by_id.setdefault(key, []).append(row)
    return rows_by_id


def trim_allergies(rows):
    # Keep every allergy row (rule 2). Each keeps its name, category, reactions with severity where given,
    # start date, and whether it is still active (no STOP date).
    out = []
    for row in rows:
        reactions = []
        for number in ("1", "2"):
            reaction = row[f"DESCRIPTION{number}"].strip()
            if reaction:
                reactions.append({
                    "reaction": reaction,
                    "severity": row[f"SEVERITY{number}"].strip() or None,
                })
        out.append({
            "name": row["DESCRIPTION"].strip(),
            "category": row["CATEGORY"].strip() or None,
            "reactions": reactions,
            "start": iso(to_date(row["START"], "allergies START")),
            "active": row["STOP"].strip() == "",
        })
    out.sort(key=lambda item: (item["start"] or "", item["name"]))
    return out


def trim_diagnoses(rows):
    # Keep every active condition (rule 3): no STOP date. Real illnesses in this data often have no suffix
    # ("Hypertension", "Diabetes"), so the suffix is not required. Drop these instead:
    # descriptions ending in "(finding)", "(person)" or "(situation)" (social notes and similar),
    # and descriptions starting with "History of" (resolved past illnesses).
    out = []
    for row in rows:
        description = row["DESCRIPTION"].strip()
        if row["STOP"].strip() or description.endswith(DIAGNOSIS_EXCLUDED_SUFFIXES):
            continue
        if description.startswith(DIAGNOSIS_EXCLUDED_PREFIX):
            continue
        out.append({
            "description": description,
            "code": row["CODE"].strip(),
            "start": iso(to_date(row["START"], "conditions START")),
        })
    out.sort(key=lambda item: (item["start"] or "", item["description"]))
    return out


def trim_medicines(rows):
    # Work out current medicines (rule 4), stopped medicines (rule 5), and dose changes (rule 6).
    # A medicine is matched on its exact description.
    by_description = {}
    for row in rows:
        description = row["DESCRIPTION"].strip()
        if description:
            by_description.setdefault(description, []).append(row)

    # Rule 4: current if some row has no STOP date and started inside the window.
    # Very old open rows (before the window) do not count as current.
    current = []
    current_descriptions = set()
    for description, group in by_description.items():
        live = []
        for row in group:
            start = to_date(row["START"], "medications START")
            if not row["STOP"].strip() and in_window(start):
                live.append((start, row))
        if not live:
            continue
        # Keep the latest prescription: the row with the most recent start date.
        start, row = max(live, key=lambda item: item[0])
        current_descriptions.add(description)
        current.append({
            "description": description,
            "code": row["CODE"].strip(),
            "start": iso(start),
            "reason": row["REASONDESCRIPTION"].strip() or None,
        })
    current.sort(key=lambda item: item["description"])

    # Rule 5: stopped if some row's STOP date is inside the window and the patient is not on it now.
    # A refill (one row ends, the same medicine starts again) is not a stop, because it is still current.
    stopped = []
    for description, group in by_description.items():
        if description in current_descriptions:
            continue
        stops = []
        for row in group:
            stop = to_date(row["STOP"], "medications STOP")
            if in_window(stop):
                stops.append((stop, row))
        if not stops:
            continue
        # Keep the last stop date.
        stop, row = max(stops, key=lambda item: item[0])
        stopped.append({
            "description": description,
            "code": row["CODE"].strip(),
            "last_stop": iso(stop),
        })
    stopped.sort(key=lambda item: item["description"])
    return current, stopped


def find_dose_changes(current, stopped):
    # Rule 6: a current and a stopped medicine with the same name but a different strength.
    # Only the simple name match is used. Formulation words are ignored.
    changes = []
    for now in current:
        now_name, now_strength = split_medicine(now["description"])
        for before in stopped:
            old_name, old_strength = split_medicine(before["description"])
            same_name = now_name.lower() == old_name.lower()
            if same_name and now_strength and old_strength and now_strength != old_strength:
                changes.append({
                    "name": now_name,
                    "current": {"description": now["description"], "strength": now_strength},
                    "stopped": {
                        "description": before["description"],
                        "strength": old_strength,
                        "last_stop": before["last_stop"],
                    },
                })
    return changes


def build_record(split_row, patient_row, allergy_rows, condition_rows, medication_rows):
    # Assemble one patient's trimmed record. The basics come first, then the four trimmed lists.
    patient_id = split_row["patient_id"]
    synthea_id = split_row["synthea_id"]

    # Check the split file agrees with the raw patient file. A mismatch means the split is wrong, so stop.
    if patient_row["GENDER"] != split_row["sex"]:
        raise ValueError(f"Sex in split does not match raw file for {patient_id}")
    birth = to_date(patient_row["BIRTHDATE"], "patients BIRTHDATE")
    age = age_on(birth, REFERENCE_DATE)
    band = age_band_for(age)
    if band != split_row["age_band"]:
        raise ValueError(f"Age band in split does not match raw file for {patient_id}")

    current, stopped = trim_medicines(medication_rows)
    return {
        "patient_id": patient_id,
        "synthea_id": synthea_id,
        "sex": patient_row["GENDER"].strip(),
        "birth_date": iso(birth),
        "age_on_reference_date": age,
        "age_band": band,
        # Synthea adds trailing digits to some names, e.g. "Asia282". They are removed here.
        "first_name": TRAILING_DIGITS.sub("", patient_row["FIRST"].strip()),
        "last_name": TRAILING_DIGITS.sub("", patient_row["LAST"].strip()),
        "window": {"reference_date": iso(REFERENCE_DATE), "window_start": iso(WINDOW_START)},
        "allergies": trim_allergies(allergy_rows),
        "diagnoses": trim_diagnoses(condition_rows),
        "current_medicines": current,
        "stopped_medicines": stopped,
        "dose_changes": find_dose_changes(current, stopped),
    }


def write_record(split_name, patient_id, record):
    # Write the record as UTF-8 JSON to <split>/<patient>/<patient>_synthea.json. Creates the folder if needed.
    folder = OUT_DIRS[split_name] / patient_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{patient_id}_synthea.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return path


def main():
    # Command-line options. --test runs only the two working patients P001 and P002.
    parser = argparse.ArgumentParser(description="Trim Synthea histories to the 5-year window (T11).")
    parser.add_argument("--test", action="store_true", help="only P001 and P002 (working patients)")
    args = parser.parse_args()

    # Choose which patients to run: working, held-out and reserve (T59 added reserve to held-out).
    split_rows = read_split()
    if args.test:
        split_rows = [row for row in split_rows if row["patient_id"] in TEST_PATIENTS]
    wanted = {row["synthea_id"] for row in split_rows}

    # Read the raw files once, keeping only the rows for the chosen patients.
    with (RAW_CSV_DIR / "patients.csv").open(encoding="utf-8", newline="") as handle:
        patients = {row["Id"]: row for row in csv.DictReader(handle) if row["Id"] in wanted}
    allergies = read_raw_rows("allergies.csv", wanted, "PATIENT")
    conditions = read_raw_rows("conditions.csv", wanted, "PATIENT")
    medications = read_raw_rows("medications.csv", wanted, "PATIENT")

    # Totals for held-out patients only. Their names and values are never printed.
    held_out_totals = Counter()
    held_out_files = 0

    for split_row in split_rows:
        patient_id = split_row["patient_id"]
        synthea_id = split_row["synthea_id"]
        if synthea_id not in patients:
            raise ValueError(f"No raw patient row for {patient_id}")
        record = build_record(
            split_row,
            patients[synthea_id],
            allergies.get(synthea_id, []),
            conditions.get(synthea_id, []),
            medications.get(synthea_id, []),
        )
        write_record(split_row["split"], patient_id, record)

        counts = {
            "allergies": len(record["allergies"]),
            "current": len(record["current_medicines"]),
            "stopped": len(record["stopped_medicines"]),
            "dose_changes": len(record["dose_changes"]),
        }
        if split_row["split"] == "working":
            # Working patients may be printed one by one.
            print(
                f"{patient_id}: allergies {counts['allergies']}, "
                f"current medicines {counts['current']}, "
                f"stopped medicines {counts['stopped']}, "
                f"dose changes {counts['dose_changes']}"
            )
        else:
            # Held-out and reserve patients: add to the totals only.
            held_out_files += 1
            held_out_totals.update(counts)

    if held_out_files:
        print(
            f"Held-out and reserve: {held_out_files} files written. Totals: "
            f"allergies {held_out_totals['allergies']}, "
            f"current medicines {held_out_totals['current']}, "
            f"stopped medicines {held_out_totals['stopped']}, "
            f"dose changes {held_out_totals['dose_changes']}"
        )


if __name__ == "__main__":
    main()
