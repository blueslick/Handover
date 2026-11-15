"""Tests for score_single_notes.py (T43). Run from the repo root: .venv/bin/python -m pytest pipeline/eval/tests

Uses small made-up records. The one end-to-end test uses the public MTSamples note D212.
It never opens a held-out file.
"""

import csv
import json
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL))

import score  # noqa: E402
import score_single_notes as ssn  # noqa: E402


def fact(fact_id, type_, name, status="current", written=None, quote="q", flags=None, patient="D299"):
    """A made-up fact with every field the scoring reads."""
    return {
        "fact_id": fact_id, "patient_id": patient, "type": type_, "name": name,
        "name_as_written": written if written is not None else name,
        "dose": None, "frequency": None, "reaction": None, "status": status,
        "hospital": "A", "date": "2026-01-01", "quote": quote, "sources": [], "history": [],
        "flags": flags or [], "conflict_group": None,
    }


def record(facts, patient="D299"):
    return {"patient_id": patient, "kind": "compiled", "facts": facts}


# --- The type filter ----------------------------------------------------------------------

def test_type_filter_keeps_only_allergies_and_medicines_on_both_sides():
    key = record([fact("K1", "medicine", "aspirin"), fact("K2", "diagnosis", "asthma"),
                  fact("K3", "operation", "appendectomy"), fact("K4", "allergy", "penicillin")])
    tool = record([fact("T1", "medicine", "aspirin"), fact("T2", "diagnosis", "asthma"),
                   fact("T3", "operation", "appendectomy")])
    tool_f, key_f, removed = ssn.filter_note(tool, key, "q")
    assert [f["fact_id"] for f in key_f["facts"]] == ["K1", "K4"]
    assert [f["fact_id"] for f in tool_f["facts"]] == ["T1"]
    # Facts dropped by the type filter are not counted as removed by the zone rule.
    assert removed == 0


# --- The zone rule ------------------------------------------------------------------------

def test_zone_rule_keeps_quote_inside_and_removes_quote_outside():
    zone = "MEDICATIONS: aspirin 100 mg daily."
    facts = [fact("T1", "medicine", "aspirin", quote="aspirin 100 mg daily"),
             fact("T2", "medicine", "warfarin", quote="warfarin 5 mg")]
    kept, removed = ssn.apply_zone_rule(facts, zone)
    assert [f["fact_id"] for f in kept] == ["T1"]
    assert removed == 1


def test_zone_rule_quote_spread_over_a_line_break_is_inside():
    zone = "MEDICATIONS:  take aspirin\n   100 mg   daily"
    kept, removed = ssn.apply_zone_rule([fact("T1", "medicine", "aspirin", quote="aspirin 100 mg\ndaily")], zone)
    assert len(kept) == 1 and removed == 0


def test_zone_rule_keeps_a_fact_with_no_quote():
    facts = [fact("T1", "medicine", "aspirin", quote=None), fact("T2", "medicine", "warfarin", quote=""),
             fact("T3", "medicine", "heparin", quote="   ")]
    kept, removed = ssn.apply_zone_rule(facts, "something else")
    assert len(kept) == 3 and removed == 0


def test_zone_rule_does_not_change_the_key_side():
    key = record([fact("K1", "medicine", "aspirin", quote="not in the zone")])
    _, key_f, _ = ssn.filter_note(record([]), key, "the zone")
    assert [f["fact_id"] for f in key_f["facts"]] == ["K1"]


def test_filter_note_does_not_change_its_inputs():
    tool = record([fact("T1", "medicine", "aspirin", quote="outside"), fact("T2", "diagnosis", "asthma")])
    ssn.filter_note(tool, record([]), "zone")
    assert len(tool["facts"]) == 2


# --- Miss causes --------------------------------------------------------------------------

def causes(key_facts, tool_facts):
    key, tool = record(key_facts), record(tool_facts)
    result = score.score_patient(tool, key)
    return {row["key_fact_id"]: row["cause"] for row in ssn.miss_causes(key, tool, result)}


def test_cause_wrong_status():
    got = causes([fact("K1", "medicine", "aspirin", status="current")],
                 [fact("T1", "medicine", "aspirin", status="stopped")])
    assert got == {"K1": "wrong status"}


def test_cause_found_no_standard_name():
    # Same type and status, empty standard name, same name as written apart from case and spaces.
    got = causes([fact("K1", "medicine", "lisinopril", written="Lisinopril ")],
                 [fact("T1", "medicine", None, written=" lisinopril", flags=["unknown_name"])])
    assert got == {"K1": "found, no standard name"}


def test_cause_check_by_hand_when_nothing_was_found():
    got = causes([fact("K1", "medicine", "aspirin")], [])
    assert got == {"K1": "check by hand"}


def test_cause_check_by_hand_when_the_tool_fact_has_a_different_name_as_written():
    got = causes([fact("K1", "medicine", "lisinopril", written="Lisinopril")],
                 [fact("T1", "medicine", None, written="Zestril")])
    assert got == {"K1": "check by hand"}


def test_cause_check_by_hand_when_the_tool_fact_has_a_different_status():
    got = causes([fact("K1", "medicine", "lisinopril", written="Lisinopril", status="current")],
                 [fact("T1", "medicine", None, written="Lisinopril", status="stopped")])
    assert got == {"K1": "check by hand"}


def test_cause_check_by_hand_when_the_tool_fact_has_a_standard_name():
    # A tool fact with a name that still did not match the key is a different case.
    got = causes([fact("K1", "medicine", "lisinopril", written="Lisinopril")],
                 [fact("T1", "medicine", "enalapril", written="Lisinopril")])
    assert got == {"K1": "check by hand"}


def test_cause_check_by_hand_when_the_tool_fact_has_another_type():
    got = causes([fact("K1", "allergy", "latex", written="Latex")],
                 [fact("T1", "medicine", None, written="Latex")])
    assert got == {"K1": "check by hand"}


def test_matched_key_facts_have_no_miss_row():
    assert causes([fact("K1", "medicine", "aspirin")], [fact("T1", "medicine", "aspirin")]) == {}


def test_count_unnamed():
    facts = [fact("T1", "medicine", None, flags=["unknown_name"]), fact("T2", "allergy", None),
             fact("T3", "medicine", "aspirin")]
    assert ssn.count_unnamed(facts) == (2, 1)


# --- Command line -------------------------------------------------------------------------

@pytest.mark.parametrize("pid", ["D001", "D101", "D200", "D213", "P021", "R001"])
def test_cli_refuses_ids_outside_the_set_before_opening_anything(tmp_path, pid):
    with pytest.raises(SystemExit):
        ssn.main(["--set", "mtsamples", "--patients", pid, "--out-dir", str(tmp_path / "out")])
    assert not (tmp_path / "out").exists()


def test_cli_end_to_end_on_d212_matches_score_py_on_the_same_filtered_files(tmp_path):
    config = ssn.SETS["mtsamples"]
    out_mine = tmp_path / "mine"
    ssn.main(["--set", "mtsamples", "--patients", "D212", "--out-dir", str(out_mine)])

    # Build the same filtered files by hand and give them to score.py's own command line.
    zone_name = ssn.load_id_map(config["id_map"])["D212"]
    zone_text = (config["zones_dir"] / f"{zone_name}_zone.txt").read_text(encoding="utf-8")
    compiled = score.load_json(config["compiled_dir"] / "D212.json")
    key = score.load_json(config["keys_dir"] / "D212" / "D212_key.json")
    compiled_f, key_f, _ = ssn.filter_note(compiled, key, zone_text)
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "D212.json").write_text(json.dumps(compiled_f), encoding="utf-8")
    (plain / "D212_key.json").write_text(json.dumps(key_f), encoding="utf-8")
    out_plain = tmp_path / "plain_out"
    score.main(["--compiled-dir", str(plain), "--keys-dir", str(plain), "--patients", "D212",
                "--out-dir", str(out_plain)])

    for name in ("per_patient.csv", "summary.csv", "failures.csv"):
        assert (out_mine / name).read_text(encoding="utf-8") == (out_plain / name).read_text(encoding="utf-8"), name
    # The scored facts really are allergies and medicines only, and the extra file is there.
    assert {f["type"] for f in compiled_f["facts"]} <= {"allergy", "medicine"}
    with open(out_mine / "miss_causes.csv", encoding="utf-8", newline="") as handle:
        assert csv.DictReader(handle).fieldnames == ssn.MISS_FIELDS


def test_failures_header_matches_score_py(tmp_path):
    # score.py writes the failures.csv header inline; ours must stay the same.
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "D201.json").write_text(json.dumps(record([], "D201")), encoding="utf-8")
    (plain / "D201_key.json").write_text(json.dumps(record([], "D201")), encoding="utf-8")
    score.main(["--compiled-dir", str(plain), "--keys-dir", str(plain), "--patients", "D201",
                "--out-dir", str(tmp_path / "out")])
    with open(tmp_path / "out" / "failures.csv", encoding="utf-8", newline="") as handle:
        assert csv.DictReader(handle).fieldnames == ssn.FAILURE_FIELDS
