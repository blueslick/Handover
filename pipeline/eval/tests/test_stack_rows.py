"""Tests for stack_rows.py, the runner for build-up rows 4 to 6 (T65). Run from the repo root:
    .venv/bin/python -m pytest pipeline/eval/tests

Uses small made-up saved files in a temporary folder. It never opens a held-out file.
"""

import json
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parents[1]
SHARED = EVAL.parents[1] / "shared"
sys.path.insert(0, str(EVAL))
sys.path.insert(0, str(SHARED))

import stack_rows  # noqa: E402
import validate  # noqa: E402  (shared/validate.py)

RUN = "20261115-v2-test"


def fact(name, status="current", dose="5 mg", quote="line"):
    return {"type": "medicine", "name": name, "name_as_written": name, "dose": dose, "frequency": None,
            "reaction": None, "status": status, "date": "2021-03-02", "quote": quote, "flags": []}


# Write one saved hospital file the way the tool saves it, with a first-try marker.
def write_saved(folder, patient, hospital, facts, attempt=1, name=None):
    folder.mkdir(parents=True, exist_ok=True)
    doc = {"patient_id": patient, "hospital": hospital, "source_file": f"{patient}_{hospital}." + ("csv" if hospital == "A" else "txt"),
           "run_id": RUN, "attempt": attempt, "facts": facts}
    (folder / (name or f"{patient}_{hospital}.json")).write_text(json.dumps(doc), encoding="utf-8")


@pytest.fixture
def source(tmp_path):
    """A source root holding one complete run for P001: one fact per hospital."""
    run = tmp_path / "source" / RUN
    for hospital, drug in (("A", "warfarin"), ("B", "paracetamol"), ("C", "metformin")):
        write_saved(run, "P001", hospital, [fact(drug)])
    return tmp_path / "source"


def test_stacks_every_fact_into_a_compiled_shape_record(source, tmp_path):
    record = stack_rows.build_row_record(source, RUN, "P001")
    assert record["kind"] == "compiled"                       # no new kind name (Q12)
    assert record["run_id"] == RUN
    assert [f["name"] for f in record["facts"]] == ["warfarin", "paracetamol", "metformin"]
    assert [f["hospital"] for f in record["facts"]] == ["A", "B", "C"]
    assert record["built_from"] == ["P001_A.csv", "P001_B.txt", "P001_C.txt"]
    out = tmp_path / "out"
    stack_rows.run_row(source, RUN, ["P001"], out, hidden=False)
    assert validate.check_file(out / "P001.json", "compiled") == []


def test_attempt2_files_are_ignored(source, tmp_path):
    # A retry is saved under another name. Even with different facts it must not be read.
    write_saved(source / RUN, "P001", "A", [fact("aspirin"), fact("ibuprofen")], attempt=2,
                name="P001_A.attempt2.json")
    write_saved(source / RUN, "P001", "B", [fact("aspirin")], attempt=2, name="P001_B.attempt2.json")
    record = stack_rows.build_row_record(source, RUN, "P001")
    assert [f["name"] for f in record["facts"]] == ["warfarin", "paracetamol", "metformin"]


def test_a_saved_file_that_is_not_a_first_try_is_refused(source):
    write_saved(source / RUN, "P001", "B", [fact("paracetamol")], attempt=2)  # exact name, but attempt 2
    with pytest.raises(ValueError, match="first try"):
        stack_rows.build_row_record(source, RUN, "P001")


def test_a_file_for_another_patient_is_refused(source):
    write_saved(source / RUN, "P002", "B", [fact("paracetamol")], name="P001_B.json")
    with pytest.raises(ValueError, match="does not match"):
        stack_rows.build_row_record(source, RUN, "P001")


def test_stops_on_a_missing_file_and_writes_nothing(source, tmp_path):
    (source / RUN / "P001_B.json").unlink()
    out = tmp_path / "out"
    with pytest.raises(SystemExit) as stopped:
        stack_rows.run_row(source, RUN, ["P001"], out, hidden=False)
    assert "1 of 1 patients" in str(stopped.value)
    assert "1 files missing" in str(stopped.value)
    assert not out.exists()


def test_one_incomplete_patient_stops_the_whole_run_before_anything_is_written(source, tmp_path):
    for hospital in "AB":
        write_saved(source / RUN, "P002", hospital, [fact("paracetamol")])   # P002 has no hospital C file
    out = tmp_path / "out"
    with pytest.raises(SystemExit) as stopped:
        stack_rows.run_row(source, RUN, ["P001", "P002"], out, hidden=False)
    assert "1 of 2 patients" in str(stopped.value)
    assert not out.exists()                                    # the complete patient was not written either


def test_a_held_out_style_stop_reports_counts_only(source, tmp_path):
    (source / RUN / "P001_A.json").unlink()
    with pytest.raises(SystemExit) as stopped:
        stack_rows.run_row(source, RUN, ["P001"], tmp_path / "out", hidden=True)
    assert "P001" not in str(stopped.value)                    # no patient ID in a held-out message


def test_each_row_reads_the_right_folder():
    assert stack_rows.ROW_SOURCE[4].name == "extracted"
    assert stack_rows.ROW_SOURCE[5].name == "extracted"
    assert stack_rows.ROW_SOURCE[6].name == "checked"


def test_working_output_needs_an_explicit_out_dir(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["stack_rows.py", "--row", "5", "--run-id", RUN, "P001"])
    with pytest.raises(SystemExit):
        stack_rows.main()
