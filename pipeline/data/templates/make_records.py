"""The three hospital templates (T12). Code writes the records, not an AI.

Hospital A = CSV table, Hospital B = free-text clinic letter, Hospital C = brand-name layout.
The formats are described for the whole team in shared/hospital_formats.md.

Each template takes one "visit" (what that hospital knows about the patient on its visit date)
and returns two things:

    text     the record exactly as it is saved (P014_A.csv, P014_B.txt, P014_C.txt)
    written  one entry per fact the record states, in the compiled-record vocabulary
             (type, name, name_as_written, dose, frequency, reaction, status, date, quote).
             `quote` is copied from `text` character for character, so the answer-key
             script (T14) can use it directly and the Check step's string match will pass.

A visit looks like this (all dates YYYY-MM-DD):

    {
      "patient_id": "P001", "first_name": "...", "last_name": "...",
      "birth_date": "2003-06-04", "sex": "F",
      "hospital": "A", "visit_date": "2021-11-18",
      "allergies":  [{"synthea_name": "Aspirin", "reactions": ["Wheal (finding)"], "start": "1994-06-19"}],
      "diagnoses":  [{"description": "Hypertension", "start": "2021-07-28"}],
      "medicines":  [{"synthea_description": "lisinopril 10 MG Oral Tablet",
                      "status": "current" or "stopped", "date": "start date, or stop date if stopped",
                      "dose": "5 mg"}]     <- optional. Overrides the table's dose (T13 uses it to plant a dose change)
    }

An empty allergy list is written as "no known allergies". A visit with no current medicine
is written as "no regular medicines". Which facts go into which hospital's visit, and on which
date, is decided by the record generator (T13), not here.

Preview (writes nothing into patient folders; only working or demo patients):

    python pipeline/data/templates/make_records.py --preview P001
    python pipeline/data/templates/make_records.py --check-tables

The preview puts the patient's whole trimmed history into all three hospitals on the
reference date, just to show the three formats.
"""

import argparse
import csv
import io
import json
import random
import re
import sys
from datetime import date
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent
DATA_DIR = TEMPLATE_DIR.parent
MEDICINE_TABLE = TEMPLATE_DIR / "medicine_table.csv"
ALLERGY_TABLE = TEMPLATE_DIR / "allergy_table.csv"
REFERENCE_DATE = "2021-11-18"

# Hospital names are made up.
HOSPITAL_NAMES = {
    "A": "Northfield General Hospital",
    "B": "Riverside Community Hospital",
    "C": "Seri Bayu Medical Centre",
}

# The Hospital A CSV header. Agreed with Theo (upload screen) at T10. Changing it changes the contract.
CSV_HEADER = [
    "MRN", "PatientName", "DOB", "Sex", "EncounterDate",
    "RecordType", "Description", "Strength", "Directions", "Status", "StatusDate", "Reaction",
]

# How each hospital writes each frequency. "other" uses the medicine table's directions_other column.
FREQUENCY_WORDS = {
    "A": {"once": "once", "daily": "once daily", "twice_daily": "twice daily",
          "three_times_daily": "three times daily", "four_times_daily": "four times daily",
          "at_night": "at bedtime", "weekly": "once weekly", "as_needed": "as needed"},
    "B": {"once": "as a single dose", "daily": "once a day", "twice_daily": "twice a day",
          "three_times_daily": "three times a day", "four_times_daily": "four times a day",
          "at_night": "at night", "weekly": "once a week", "as_needed": "when needed"},
    "C": {"once": "STAT", "daily": "OD", "twice_daily": "BD", "three_times_daily": "TDS",
          "four_times_daily": "QID", "at_night": "ON", "weekly": "once weekly", "as_needed": "PRN"},
}

# Synthea reaction words, cleaned into what a hospital would write.
REACTION_WORDS = {
    "Wheal (finding)": "hives",
    "Eruption of skin (disorder)": "skin rash",
    "Allergic skin rash": "skin rash",
    "Rhinoconjunctivitis (disorder)": "hay fever symptoms",
    "Allergic angioedema (disorder)": "swelling (angioedema)",
    "Anaphylaxis (disorder)": "anaphylaxis",
    "Cough (finding)": "cough",
    "Dyspnea (finding)": "shortness of breath",
    "Finding of vomiting (finding)": "vomiting",
    "Sneezing": "sneezing",
    "Diarrhea (finding)": "diarrhoea",
    "Nose running": "runny nose",
    "Nausea (finding)": "nausea",
    "Abdominal pain (finding)": "abdominal pain",
    "Wheezing": "wheezing",
    "Wheezing (finding)": "wheezing",
    "Itching (finding)": "itching",
    "Drug-induced hyperkalemia (disorder)": "high potassium",
    "Dizziness (finding)": "dizziness",
}

DIAGNOSIS_SUFFIX = re.compile(r"\s*\((disorder|finding|situation|person|morphologic abnormality)\)\s*$")
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


# ---------- tables ----------

def load_tables():
    with MEDICINE_TABLE.open(encoding="utf-8", newline="") as handle:
        medicines = {row["synthea_description"]: row for row in csv.DictReader(handle)}
    with ALLERGY_TABLE.open(encoding="utf-8", newline="") as handle:
        allergies = {row["synthea_name"]: row for row in csv.DictReader(handle)}
    return medicines, allergies


MEDICINES, ALLERGIES = load_tables()


def medicine_info(description):
    try:
        return MEDICINES[description]
    except KeyError:
        raise KeyError("A medicine is missing from medicine_table.csv. Run --check-tables.") from None


def allergy_info(synthea_name):
    try:
        return ALLERGIES[synthea_name]
    except KeyError:
        raise KeyError("An allergy is missing from allergy_table.csv. Run --check-tables.") from None


# ---------- small helpers ----------

def to_date(text):
    return date.fromisoformat(text)


def long_date(text):          # Hospital B: 4 June 2003
    d = to_date(text)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def short_date(text):         # Hospital C: 04-Jun-2003
    d = to_date(text)
    return f"{d.day:02d}-{MONTHS[d.month - 1][:3]}-{d.year}"


def age_on(birth, on):
    b, o = to_date(birth), to_date(on)
    return o.year - b.year - ((o.month, o.day) < (b.month, b.day))


def diagnosis_name(description):
    return DIAGNOSIS_SUFFIX.sub("", description).strip()


def reaction_text(reactions):
    words = []
    for reaction in reactions:
        word = REACTION_WORDS.get(reaction, DIAGNOSIS_SUFFIX.sub("", reaction).lower())
        if word not in words:
            words.append(word)
    return words


def and_list(words):
    # ["hives"] -> "hives"; ["a", "b", "c"] -> "a, b and c"
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def frequency_words(hospital, info):
    frequency = info["frequency"] or None
    if frequency is None:
        return None
    if frequency == "other":
        return info["directions_other"] or None
    return FREQUENCY_WORDS[hospital][frequency]


def dose_for_c(dose):
    # Hospital C writes whole grams as grams ("1 g"), the trap the record format warns about.
    if not dose:
        return None
    number, unit = dose.split(" ")
    if unit == "mg" and float(number) >= 1000 and float(number) % 1000 == 0:
        return f"{int(float(number) // 1000)} g"
    return dose


def dose_of(medicine, info):
    # The visit may give its own dose (a planted dose change, T13). Otherwise use the table's dose.
    return medicine.get("dose") or info["dose"]


def generic_for_prose(generic):
    # "amoxicillin / clavulanate" -> "amoxicillin and clavulanate"
    return generic.replace(" / ", " and ")


def written(type_, name, name_as_written, status, date_, quote, dose=None, frequency=None, reaction=None):
    return {"type": type_, "name": name, "name_as_written": name_as_written, "dose": dose,
            "frequency": frequency, "reaction": reaction, "status": status, "date": date_, "quote": quote}


def split_medicines(visit):
    current = [m for m in visit["medicines"] if m["status"] == "current"]
    stopped = [m for m in visit["medicines"] if m["status"] == "stopped"]
    return current, stopped


def check_written(text, facts):
    # Every quote must be an exact piece of the record, or the answer key would be wrong.
    for fact in facts:
        if fact["quote"] not in text:
            raise AssertionError("A quote is not an exact substring of its record (template bug).")
    return text, facts


# ---------- Hospital A: CSV table ----------

def csv_line(fields):
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="").writerow(fields)
    return buffer.getvalue()


def render_a(visit):
    who = [visit["patient_id"], f'{visit["last_name"]}, {visit["first_name"]}',
           visit["birth_date"], visit["sex"], visit["visit_date"]]
    rows, facts = [], []

    def add(rest, fact):
        rows.append(csv_line(who + rest))
        if fact:
            fact["quote"] = csv_line(rest)
            facts.append(fact)

    if not visit["allergies"]:
        add(["ALLERGY", "No known allergies", "", "", "", "", ""],
            written("allergy", None, "No known allergies", "none_recorded", visit["visit_date"], None))
    for allergy in visit["allergies"]:
        info = allergy_info(allergy["synthea_name"])
        reaction = "; ".join(reaction_text(allergy["reactions"])) or None
        shown = info["name"].capitalize()
        add(["ALLERGY", shown, "", "", "Active", allergy["start"] or "", reaction or ""],
            written("allergy", info["name"], shown, "current", allergy["start"] or visit["visit_date"],
                    None, reaction=reaction))

    for diagnosis in visit["diagnoses"]:
        name = diagnosis_name(diagnosis["description"])
        add(["PROBLEM", name, "", "", "Active", diagnosis["start"] or "", ""],
            written("diagnosis", name.lower(), name, "current", diagnosis["start"] or visit["visit_date"], None))

    current, stopped = split_medicines(visit)
    if not current:
        add(["MEDICATION", "No current medications", "", "", "", "", ""],
            written("medicine", None, "No current medications", "none_recorded", visit["visit_date"], None))
    for medicine in current + stopped:
        info = medicine_info(medicine["synthea_description"])
        shown = info["generic"].capitalize()
        status = "Active" if medicine["status"] == "current" else "Discontinued"
        dose = dose_of(medicine, info)
        add(["MEDICATION", shown, dose, frequency_words("A", info) or "", status, medicine["date"], ""],
            written("medicine", info["generic"], shown, medicine["status"], medicine["date"], None,
                    dose=dose or None, frequency=info["frequency"] or None))

    text = csv_line(CSV_HEADER) + "\n" + "\n".join(rows) + "\n"
    return check_written(text, facts)


# ---------- Hospital B: free-text clinic letter ----------

def render_b(visit):
    rng = random.Random(f'{visit["patient_id"]}-B')     # same patient, same wording, every run
    female = visit["sex"] == "F"
    age = age_on(visit["birth_date"], visit["visit_date"])
    she, her = ("She", "Her") if female else ("He", "His")
    person = ("woman" if female else "man") if age >= 18 else ("girl" if female else "boy")
    facts, sentences = [], []
    paragraphs = [sentences]

    def new_paragraph():
        nonlocal sentences
        sentences = []
        paragraphs.append(sentences)

    def say(sentence, fact=None):
        sentences.append(sentence)
        if fact:
            fact["quote"] = sentence
            facts.append(fact)

    say(f"I reviewed this {age}-year-old {person} in the medical clinic today.")

    for diagnosis in visit["diagnoses"]:
        name = diagnosis_name(diagnosis["description"])
        opener = rng.choice([f"{she} has a history of", f"{her} background includes", f"{she} is known to have"])
        say(f"{opener} {name.lower()}.",
            written("diagnosis", name.lower(), name.lower(), "current", visit["visit_date"], None))

    new_paragraph()
    if not visit["allergies"]:
        say(f"{she} has no known allergies.",
            written("allergy", None, "no known allergies", "none_recorded", visit["visit_date"], None))
    for allergy in visit["allergies"]:
        info = allergy_info(allergy["synthea_name"])
        reactions = reaction_text(allergy["reactions"])
        if reactions:
            sentence = f"{she} is allergic to {info['name']}, which causes {and_list(reactions)}."
        else:
            sentence = f"{she} is allergic to {info['name']}."
        say(sentence, written("allergy", info["name"], info["name"], "current", visit["visit_date"], None,
                              reaction=", ".join(reactions) or None))

    new_paragraph()
    current, stopped = split_medicines(visit)
    if not current:
        say(f"{she} takes no regular medicines.",
            written("medicine", None, "no regular medicines", "none_recorded", visit["visit_date"], None))
    for medicine in current:
        info = medicine_info(medicine["synthea_description"])
        name = generic_for_prose(info["generic"])
        dose = dose_of(medicine, info)
        parts = [name] + ([dose] if dose else [])
        how = frequency_words("B", info)
        if how:
            parts.append(how)
        opener = rng.choice([f"{she} takes", f"{she} is on", f"{she} continues on"])
        say(f"{opener} {' '.join(parts)}.",
            written("medicine", info["generic"], name, "current", visit["visit_date"], None,
                    dose=dose or None, frequency=info["frequency"] or None))
    for medicine in stopped:
        info = medicine_info(medicine["synthea_description"])
        name = generic_for_prose(info["generic"])
        say(f"{her} {name} was stopped on {long_date(medicine['date'])}.",
            written("medicine", info["generic"], name, "stopped", medicine["date"], None))

    new_paragraph()
    say("Plan: no changes today. Review in clinic in three months.")

    letter = [
        HOSPITAL_NAMES["B"].upper(),
        "Medical Outpatient Clinic",
        "",
        f'Patient: {visit["first_name"]} {visit["last_name"]}',
        f'Hospital ID: {visit["patient_id"]}',
        f'Date of birth: {long_date(visit["birth_date"])}',
        f'Date of visit: {long_date(visit["visit_date"])}',
        "",
        "Dear Doctor,",
        "",
        "\n\n".join(" ".join(p) for p in paragraphs if p),
        "",
        "Yours sincerely,",
        "Medical Outpatient Clinic",
        "",
    ]
    return check_written("\n".join(letter), facts)


# ---------- Hospital C: brand-name layout ----------

def render_c(visit):
    facts, lines = [], []

    def line(text, fact=None):
        lines.append(text)
        if fact:
            fact["quote"] = text.strip()
            facts.append(fact)

    rule = "=" * 56
    line(rule)
    line(f' {HOSPITAL_NAMES["C"].upper()}')
    line(" MEDICATION RECONCILIATION SHEET")
    line(rule)
    line(f' Name    : {visit["first_name"].upper()} {visit["last_name"].upper()}')
    line(f' ID      : {visit["patient_id"]}')
    line(f' DOB     : {short_date(visit["birth_date"])}    Sex: {visit["sex"]}')
    line(f' Date    : {short_date(visit["visit_date"])}')
    line(rule)

    line("")
    line("[ALLERGIES]")
    if not visit["allergies"]:
        line("  - NKA", written("allergy", None, "NKA", "none_recorded", visit["visit_date"], None))
    for allergy in visit["allergies"]:
        info = allergy_info(allergy["synthea_name"])
        shown = info["brand"] or info["name"].capitalize()
        reactions = reaction_text(allergy["reactions"])
        text = f"  - {shown}" + (f" ({', '.join(reactions)})" if reactions else "")
        line(text, written("allergy", info["name"], shown, "current", visit["visit_date"], None,
                           reaction=", ".join(reactions) or None))

    line("")
    line("[PROBLEM LIST]")
    if not visit["diagnoses"]:
        line("  - Nil")
    for diagnosis in visit["diagnoses"]:
        name = diagnosis_name(diagnosis["description"])
        line(f"  - {name}", written("diagnosis", name.lower(), name, "current", visit["visit_date"], None))

    current, stopped = split_medicines(visit)
    line("")
    line("[CURRENT MEDICATIONS]")
    if not current:
        line("  Nil regular medications",
             written("medicine", None, "Nil regular medications", "none_recorded", visit["visit_date"], None))
    for number, medicine in enumerate(current, 1):
        info = medicine_info(medicine["synthea_description"])
        shown = info["brand"] or info["generic"].capitalize()
        dose = dose_of(medicine, info)
        parts = [shown]
        if dose_for_c(dose):
            parts.append(dose_for_c(dose))
        if frequency_words("C", info):
            parts.append(frequency_words("C", info))
        line(f"  {number}. {' '.join(parts)}",
             written("medicine", info["generic"], shown, "current", visit["visit_date"], None,
                     dose=dose or None, frequency=info["frequency"] or None))

    if stopped:
        line("")
        line("[DISCONTINUED]")
    for number, medicine in enumerate(stopped, 1):
        info = medicine_info(medicine["synthea_description"])
        shown = info["brand"] or info["generic"].capitalize()
        line(f"  {number}. {shown} - stopped {short_date(medicine['date'])}",
             written("medicine", info["generic"], shown, "stopped", medicine["date"], None))

    line("")
    line(rule)
    line(" Reconciled by: Pharmacy, Seri Bayu Medical Centre")
    line(rule)
    line("")
    return check_written("\n".join(lines), facts)


RENDERERS = {"A": render_a, "B": render_b, "C": render_c}
FILE_ENDINGS = {"A": "_A.csv", "B": "_B.txt", "C": "_C.txt"}


def render(visit):
    return RENDERERS[visit["hospital"]](visit)


# ---------- preview and table check ----------

def find_patient_file(patient_id):
    for folder in ("working", "demo"):
        path = DATA_DIR / folder / patient_id / f"{patient_id}_synthea.json"
        if path.exists():
            return path
    sys.exit("Preview works on working and demo patients only. Held-out patients are never opened.")


def full_snapshot(trimmed, hospital, visit_date=REFERENCE_DATE):
    # Everything in the trimmed history, as one hospital would see it on visit_date. Preview only.
    return {
        "patient_id": trimmed["patient_id"], "first_name": trimmed["first_name"],
        "last_name": trimmed["last_name"], "birth_date": trimmed["birth_date"], "sex": trimmed["sex"],
        "hospital": hospital, "visit_date": visit_date,
        "allergies": [{"synthea_name": a["name"], "reactions": [r["reaction"] for r in a["reactions"]],
                       "start": a["start"]} for a in trimmed["allergies"] if a["active"]],
        "diagnoses": [{"description": d["description"], "start": d["start"]} for d in trimmed["diagnoses"]],
        "medicines": [{"synthea_description": m["description"], "status": "current", "date": m["start"]}
                      for m in trimmed["current_medicines"]]
                     + [{"synthea_description": m["description"], "status": "stopped", "date": m["last_stop"]}
                        for m in trimmed["stopped_medicines"]],
    }


def check_tables():
    # Every medicine and allergy in every trimmed patient must be in the tables.
    # Only counts are printed, so nothing from a held-out patient is shown.
    missing_medicines = missing_allergies = patients = 0
    paths = (sorted(DATA_DIR.glob("*/P*/P*_synthea.json")) + sorted(DATA_DIR.glob("reserve/R*/R*_synthea.json"))
             + sorted(DATA_DIR.glob("demo/*/*_synthea.json")))
    for path in paths:
        trimmed = json.loads(path.read_text(encoding="utf-8"))
        patients += 1
        for m in trimmed["current_medicines"] + trimmed["stopped_medicines"]:
            missing_medicines += m["description"] not in MEDICINES
        for a in trimmed["allergies"]:
            missing_allergies += a["name"] not in ALLERGIES
    print(f"Checked {patients} patients: {missing_medicines} medicines and {missing_allergies} allergies "
          "missing from the tables.")
    for row in MEDICINES.values():
        if row["frequency"] and row["frequency"] not in FREQUENCY_WORDS["A"] and row["frequency"] != "other":
            print("Bad frequency in medicine_table.csv:", row["synthea_description"])
        if row["dose"] and not re.fullmatch(r"\d+(\.\d+)? (mg|mcg|g|mL|units|puffs|drops)", row["dose"]):
            print("Bad dose in medicine_table.csv:", row["synthea_description"])
    return missing_medicines + missing_allergies == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--preview", metavar="PATIENT_ID", help="print all three formats for one working patient")
    parser.add_argument("--written", action="store_true", help="with --preview, also print the written facts")
    parser.add_argument("--check-tables", action="store_true")
    args = parser.parse_args()
    if args.check_tables:
        sys.exit(0 if check_tables() else 1)
    if args.preview:
        trimmed = json.loads(find_patient_file(args.preview).read_text(encoding="utf-8"))
        for hospital in "ABC":
            text, facts = render(full_snapshot(trimmed, hospital))
            print(f"----- {args.preview}{FILE_ENDINGS[hospital]} -----")
            print(text)
            if args.written:
                print(json.dumps(facts, indent=1, ensure_ascii=False))
        return
    parser.print_help()


if __name__ == "__main__":
    main()
