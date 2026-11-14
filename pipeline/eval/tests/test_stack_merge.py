"""Tests for stack_merge.py (T24). Run from the repo root: .venv/bin/python -m pytest pipeline/eval/tests"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # pipeline/eval, so stack_merge imports

from stack_merge import stack_merge  # noqa: E402


# A tiny extracted-shape record from one hospital, for testing the merge only.
def extraction(hospital, facts, patient="P001"):
    return {"patient_id": patient, "hospital": hospital, "source_file": f"{patient}_{hospital}.txt", "facts": facts}


# A tiny extracted-shape medicine fact.
def medicine(name, date="2021-07-14"):
    return {
        "type": "medicine", "name": name, "name_as_written": name, "dose": "5 mg",
        "frequency": None, "reaction": None, "status": "current", "date": date,
        "quote": f"takes {name} 5 mg", "flags": [],
    }


def test_same_drug_in_two_hospitals_stays_as_two_entries():
    merged = stack_merge("P001", [
        extraction("B", [medicine("warfarin")]),
        extraction("A", [medicine("warfarin")]),
    ])
    assert len(merged) == 2                                  # no deduplication
    assert [f["fact_id"] for f in merged] == ["P001-F01", "P001-F02"]
    assert [f["hospital"] for f in merged] == ["A", "B"]     # A, B, C order, whatever the input order
    for fact in merged:
        assert len(fact["sources"]) == 1                     # one source per entry
        assert fact["conflict_group"] is None                # no conflict logic
        assert fact["flags"] == []                           # no conflict flags added


def test_refuses_a_record_from_another_patient():
    with pytest.raises(ValueError):
        stack_merge("P001", [extraction("A", [medicine("warfarin")], patient="P002")])
