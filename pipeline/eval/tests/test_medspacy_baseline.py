"""Tests for medspacy_baseline.py (T42). Run from the repo root: .venv/bin/python -m pytest pipeline/eval/tests

Skipped if medspacy is not installed (it is optional: pip install medspacy==1.3.1).
"""

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("medspacy")

EVAL = Path(__file__).resolve().parents[1]
SHARED = EVAL.parents[1] / "shared"
sys.path.insert(0, str(EVAL))
sys.path.insert(0, str(SHARED))

import medspacy_baseline as mb  # noqa: E402
import validate  # noqa: E402  (shared/validate.py)

NAMES = mb.load_names()
KINDS = mb.load_kinds()
NLP = mb.build_nlp(NAMES)


def facts_from(tmp_path, body, hospital="B"):
    header = {"B": "Date of visit: 14 July 2021\n", "C": " Date    : 14-Jul-2021\n"}[hospital]
    path = tmp_path / f"T001_{hospital}.txt"
    path.write_text(header + body, encoding="utf-8")
    return mb.extract_record(path, hospital, NAMES, KINDS, NLP)


def test_brand_becomes_generic_and_keeps_the_dose(tmp_path):
    [fact] = facts_from(tmp_path, "1. Panadol 1 g PRN\n", hospital="C")
    assert (fact["type"], fact["name"], fact["dose"], fact["status"]) == ("medicine", "paracetamol", "1 g", "current")


def test_stopped_sentence_marks_only_that_medicine(tmp_path):
    facts = facts_from(tmp_path, "She takes metformin 1000 mg twice a day. Her warfarin was stopped on 20 June 2021.\n")
    by_name = {f["name"]: f["status"] for f in facts}
    assert by_name == {"metformin": "current", "warfarin": "stopped"}


def test_no_known_allergies_is_none_recorded(tmp_path):
    [fact] = facts_from(tmp_path, "She has no known allergies.\n")
    assert (fact["type"], fact["name"], fact["status"]) == ("allergy", None, "none_recorded")


def test_letter_combination_written_with_and(tmp_path):
    facts = facts_from(tmp_path, "He takes no regular medicines. His amoxicillin and clavulanate was stopped on 8 February 2019.\n")
    pairs = sorted((f["type"], f["name"] or "", f["status"]) for f in facts)
    assert pairs == [("medicine", "", "none_recorded"), ("medicine", "amoxicillin / clavulanate", "stopped")]


def test_brand_sheet_sections(tmp_path):
    body = "[ALLERGIES]\n  - NKA\n\n[CURRENT MEDICATIONS]\n  Nil regular medications\n\n[DISCONTINUED]\n  1. Panadol - stopped 18-Oct-2017\n"
    pairs = sorted((f["type"], f["name"] or "", f["status"]) for f in facts_from(tmp_path, body, hospital="C"))
    assert pairs == [("allergy", "", "none_recorded"), ("medicine", "", "none_recorded"), ("medicine", "paracetamol", "stopped")]


def test_demo_patient_validates(tmp_path):
    record = mb.run_patient("D001", NAMES, KINDS, NLP)
    out = tmp_path / "D001.json"
    mb.write_record(record, out)
    assert record["kind"] == "baseline_medspacy"
    assert validate.check_file(out, "compiled") == []
    statuses = {(f["hospital"], f["name"]): f["status"] for f in json.loads(out.read_text())["facts"]}
    assert statuses[("B", "warfarin")] == "stopped"
    assert statuses[("A", "penicillin")] == "current"


def test_held_out_ids_are_refused(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["medspacy_baseline.py", "P021"])
    with pytest.raises(SystemExit):
        mb.main()
