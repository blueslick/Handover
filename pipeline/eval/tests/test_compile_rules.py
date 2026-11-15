"""Abby's compile-rule tests (T17): one test per compile rule.

The expected results come from the six rules in the plan and shared/record_format.md,
not from pipeline/tool/compile.py. Made-up facts under the demo ID D001; no real or
held-out data is read.

Run from the repo root: .venv/bin/python -m pytest pipeline/eval/ -v
"""
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "pipeline" / "tool"))  # compile.py
sys.path.insert(0, str(REPO / "shared"))             # validate.py and the schemas

from compile import compile_patient  # noqa: E402
from validate import check_file  # noqa: E402

PID = "D001"


def fact(type_, name, status="current", dose=None, date="2021-01-01", reaction=None,
         written=None, quote=None):
    """One fact in the checked shape: name is the generic, name_as_written is the source's word."""
    return {"type": type_, "name": name, "name_as_written": written or name,
            "dose": dose, "frequency": None, "reaction": reaction, "status": status,
            "date": date, "quote": quote or f"{written or name} {status}", "flags": []}


def record(hospital, *facts):
    """One extracted record (shared/schema/extracted.schema.json) from one hospital."""
    return {"format_version": "1.0", "patient_id": PID, "hospital": hospital,
            "source_file": f"{PID}_{hospital}.{'csv' if hospital == 'A' else 'txt'}",
            "run_id": "t17-test", "model": "claude-sonnet-5-5", "prompt_version": "v1",
            "temperature": None, "attempt": 1,
            "usage": {"input_tokens": 0, "output_tokens": 0}, "facts": list(facts)}


def valid(doc, kind):
    """Fail the test unless the document passes the shared schema and cross-field checks."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as fh:
        json.dump(doc, fh)
    try:
        problems = check_file(fh.name, kind)
    finally:
        Path(fh.name).unlink()
    assert problems == [], problems


def compile_records(*records):
    """Check every input record, compile them, check the output, return its facts."""
    for r in records:
        valid(r, "extracted")
    out = compile_patient(PID, list(records))
    valid(out, "compiled")
    return out["facts"]


def named(facts, name):
    return [f for f in facts if f["name"] == name]


# Rule 1, same drug one fact: Glucophage is metformin, so A and C make ONE fact listing both as sources.
def test_rule1_same_drug_one_fact():
    facts = compile_records(
        record("A", fact("medicine", "metformin", dose="500 mg", date="2021-01-10")),
        record("C", fact("medicine", "metformin", written="Glucophage", dose="500 mg", date="2021-03-01")),
    )
    assert len(facts) == 1
    [m] = named(facts, "metformin")
    assert sorted(s["hospital"] for s in m["sources"]) == ["A", "C"]
    assert m["history"] == []


# Rule 1, brand in the name field (Q02): Hospital A's name field is the brand "Glucophage" itself, so
# canonical_name() must find it in the brand table. Glucophage in A and metformin in C make ONE fact.
# The shared format says an extracted name must be a lowercase generic, so this record is NOT valid
# input (real records keep the brand in name_as_written). It is fed straight to compile_patient to
# test canonical_name()'s first lookup on its own. Only the compiled output is schema-checked.
def test_rule1_brand_in_name_field_one_fact():
    records = [
        record("A", fact("medicine", "Glucophage", dose="500 mg", date="2021-01-10")),
        record("C", fact("medicine", "metformin", dose="500 mg", date="2021-03-01")),
    ]
    out = compile_patient(PID, records)
    valid(out, "compiled")
    facts = out["facts"]
    assert len(facts) == 1
    [m] = named(facts, "metformin")
    assert sorted(s["hospital"] for s in m["sources"]) == ["A", "C"]
    assert m["history"] == []
    assert "unknown_name" not in m["flags"]


# Rule 2, explicit stop: a later "stopped" wins and the earlier current entry is kept in history.
def test_rule2_explicit_stop():
    facts = compile_records(
        record("A", fact("medicine", "warfarin", dose="5 mg", date="2021-01-10")),
        record("B", fact("medicine", "warfarin", status="stopped", date="2021-02-01")),
    )
    [w] = named(facts, "warfarin")
    assert w["status"] == "stopped"
    assert [(h["status"], h["hospital"]) for h in w["history"]] == [("current", "A")]


# Rule 3, dose change: the newer dose is the fact's dose, the old one moves to history, dose_changed is flagged.
def test_rule3_dose_change():
    facts = compile_records(
        record("A", fact("medicine", "metformin", dose="500 mg", date="2021-01-10")),
        record("B", fact("medicine", "metformin", dose="1000 mg", date="2021-02-01")),
    )
    [m] = named(facts, "metformin")
    assert m["dose"] == "1000 mg"
    assert m["status"] == "current"
    assert [h["dose"] for h in m["history"]] == ["500 mg"]
    assert "dose_changed" in m["flags"]


# Rule 4, silence is not a stop: a later record that does not mention warfarin leaves it current, dated to A.
def test_rule4_silence_is_not_a_stop():
    facts = compile_records(
        record("A", fact("medicine", "warfarin", dose="5 mg", date="2021-01-10")),
        record("C", fact("medicine", "metformin", dose="500 mg", date="2021-03-01")),
    )
    [w] = named(facts, "warfarin")
    assert w["status"] == "current"
    assert (w["hospital"], w["date"]) == ("A", "2021-01-10")
    assert [s["hospital"] for s in w["sources"]] == ["A"]


# Rule 5, allergy never removed: a penicillin allergy and "no known allergies" both stay, as one conflict.
def test_rule5_allergy_never_removed():
    facts = compile_records(
        record("A", fact("allergy", "penicillin", reaction="rash", date="2021-03-02")),
        record("B", fact("allergy", None, status="none_recorded", date="2021-07-14",
                         quote="No known allergies")),
    )
    assert len(facts) == 2
    [pen] = named(facts, "penicillin")
    [nka] = [f for f in facts if f["status"] == "none_recorded"]
    assert pen["status"] == "current"
    assert pen["conflict_group"] is not None
    assert pen["conflict_group"] == nka["conflict_group"]
    assert "conflict" in pen["flags"] and "conflict" in nka["flags"]


# Rule 6, other critical disagreement: paracetamol current and stopped on the same date; both kept, flagged, no silent winner.
def test_rule6_other_disagreement_keeps_both_sides():
    facts = compile_records(
        record("A", fact("medicine", "paracetamol", dose="1000 mg", date="2021-01-10")),
        record("B", fact("medicine", "paracetamol", status="stopped", date="2021-01-10")),
    )
    assert len(facts) == 2
    assert {f["status"] for f in facts} == {"current", "stopped"}
    groups = {f["conflict_group"] for f in facts}
    assert len(groups) == 1 and None not in groups
    assert all("conflict" in f["flags"] for f in facts)
