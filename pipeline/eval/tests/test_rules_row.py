"""Tests for rules_row.py (T24). Run from the repo root: .venv/bin/python -m pytest pipeline/eval/tests"""

import copy
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL))

import rules_row  # noqa: E402
import keyword_baseline as kb  # noqa: E402

NAMES = kb.load_names()
KINDS = kb.load_kinds()
PATTERN = kb.build_pattern(NAMES)


def test_d001_builds_a_rules_row_record_from_three_hospital_records():
    record = rules_row.build_rules_row("D001", NAMES, KINDS, PATTERN)
    assert record["kind"] == rules_row.KIND
    assert record["built_from"] == ["D001_A.csv", "D001_B.txt", "D001_C.txt"]
    assert record["facts"]
    assert all(f["patient_id"] == "D001" for f in record["facts"])


def test_each_hospital_record_goes_to_compile_patient_unchanged(monkeypatch):
    # Spy on compile_patient: it must receive the keyword facts of each record, unchanged.
    expected = rules_row.keyword_records("D001", NAMES, KINDS, PATTERN)
    seen = {}

    def spy(patient_id, records, run_id=None):
        seen["patient_id"] = patient_id
        seen["records"] = copy.deepcopy(records)
        return {"kind": "compiled", "facts": []}

    monkeypatch.setattr(rules_row, "compile_patient", spy)
    rules_row.build_rules_row("D001", NAMES, KINDS, PATTERN)
    assert seen["patient_id"] == "D001"
    assert [r["hospital"] for r in seen["records"]] == ["A", "B", "C"]
    assert seen["records"] == expected


def test_no_model_or_api_code_in_the_rules_row():
    source = (EVAL / "rules_row.py").read_text(encoding="utf-8")
    assert "anthropic" not in source
    assert "saved_calls" not in source
    assert "outputs" + "/extracted" not in source  # never reads Claude's saved extractions


def test_refuses_held_out_and_reserve_ids(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["rules_row.py", "P021"])
    with pytest.raises(SystemExit):
        rules_row.main()
    monkeypatch.setattr(sys, "argv", ["rules_row.py", "R001"])
    with pytest.raises(SystemExit):
        rules_row.main()
