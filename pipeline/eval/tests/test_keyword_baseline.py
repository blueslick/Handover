"""Tests for keyword_baseline.py (T24). Run from the repo root: .venv/bin/python -m pytest pipeline/eval/tests"""

import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parents[1]
SHARED = EVAL.parents[1] / "shared"
sys.path.insert(0, str(EVAL))
sys.path.insert(0, str(SHARED))

import keyword_baseline as kb  # noqa: E402
import validate  # noqa: E402  (shared/validate.py)

NAMES = kb.load_names()
KINDS = kb.load_kinds()
PATTERN = kb.build_pattern(NAMES)


# Write a tiny hospital B note in a temporary folder and run the keyword pass on it.
def facts_from(tmp_path, body, hospital="B"):
    path = tmp_path / f"T001_{hospital}.txt"
    path.write_text("Date of visit: 14 July 2021\n" + body, encoding="utf-8")
    return kb.extract_record(path, hospital, NAMES, KINDS, PATTERN)


def test_brand_becomes_generic_and_keeps_the_dose(tmp_path):
    [fact] = facts_from(tmp_path, "Panadol 1 g PRN")
    assert fact["type"] == "medicine"
    assert fact["name"] == "paracetamol"
    assert fact["name_as_written"] == "Panadol"
    assert fact["dose"] == "1 g"
    assert fact["status"] == "current"
    assert fact["date"] == "2021-07-14"
    assert fact["flags"] == []


def test_longest_name_wins(tmp_path):
    [fact] = facts_from(tmp_path, "amoxicillin / clavulanate 1000 mg")
    assert fact["name"] == "amoxicillin / clavulanate"


def test_allergy_line_becomes_an_allergy_with_no_dose(tmp_path):
    [fact] = facts_from(tmp_path, "ALLERGY: penicillin, skin rash")
    assert fact["type"] == "allergy"
    assert fact["name"] == "penicillin"
    assert fact["dose"] is None
    assert fact["flags"] == []


def test_allergy_only_word_is_an_allergy_without_the_word_allergy(tmp_path):
    # "egg" is allergy-only in the drug list, so this line needs no "allerg" to be an allergy.
    [fact] = facts_from(tmp_path, "Hives after egg.")
    assert fact["type"] == "allergy"
    assert fact["name"] == "egg"
    assert fact["flags"] == []


def test_brand_of_an_allergy_only_drug_is_an_allergy(tmp_path):
    # Disprin is aspirin, and aspirin is allergy-only in the drug list.
    [fact] = facts_from(tmp_path, "Disprin 300 mg")
    assert fact["type"] == "allergy"
    assert fact["name"] == "aspirin"
    assert fact["dose"] is None


def test_medicine_only_name_without_allerg_stays_a_medicine(tmp_path):
    [fact] = facts_from(tmp_path, "Warfarin 5 mg daily")
    assert fact["type"] == "medicine"
    assert fact["dose"] == "5 mg"


def test_name_listed_as_both_kinds_follows_the_allerg_word(tmp_path):
    # Lisinopril is listed as both a medicine and an allergy, so the line decides.
    [as_medicine] = facts_from(tmp_path, "Lisinopril 10 mg")
    assert as_medicine["type"] == "medicine"
    [as_allergy] = facts_from(tmp_path, "Allergic to lisinopril")
    assert as_allergy["type"] == "allergy"


def test_medicine_with_no_dose_gets_missing_dose(tmp_path):
    [fact] = facts_from(tmp_path, "She takes warfarin.")
    assert fact["dose"] is None
    assert fact["flags"] == ["missing_dose"]


def test_stop_wording_is_ignored(tmp_path):
    # No stop logic: "stopped" does not change the status.
    [fact] = facts_from(tmp_path, "Her warfarin was stopped on 20 June 2021.")
    assert fact["status"] == "current"


def test_demo_patient_warfarin_is_current_and_the_file_validates(tmp_path):
    # End to end on the demo patient (Nora). The baseline should keep warfarin as current.
    record = kb.run_patient("D001", NAMES, KINDS, PATTERN)
    warfarin = [f for f in record["facts"] if f["name"] == "warfarin"]
    assert warfarin and all(f["status"] == "current" for f in warfarin)
    # Write to a temporary folder and check it against the shared compiled schema and rules.
    out = tmp_path / "D001.json"
    kb.write_record(record, out)
    assert validate.check_file(out, "compiled") == []


def test_only_demo_and_working_ids_are_allowed():
    assert "P021" not in kb.ALLOWED and "R001" not in kb.ALLOWED
    assert len(kb.WORKING) == 20
