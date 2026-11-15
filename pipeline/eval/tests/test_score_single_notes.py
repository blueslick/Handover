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


# --- Traps (T40): background line, two parts, pairs ---------------------------------------

def atorva(fact_id, status="current"):
    return fact(fact_id, "medicine", "atorvastatin", status=status)


def test_split_note_separates_the_background_line_on_both_sides():
    key = record([atorva("K1"), fact("K2", "allergy", "penicillin"), fact("K3", "medicine", "aspirin")])
    tool = record([atorva("T1"), fact("T2", "medicine", "Atorvastatin ")])
    parts = ssn.split_note(tool, key)
    assert [f["fact_id"] for f in parts["background"][1]["facts"]] == ["K1"]
    assert [f["fact_id"] for f in parts["tested"][1]["facts"]] == ["K2", "K3"]
    # The name is matched without regard to case or spaces; both tool facts are background.
    assert [f["fact_id"] for f in parts["background"][0]["facts"]] == ["T1", "T2"]
    assert parts["tested"][0]["facts"] == []


def test_an_allergy_named_atorvastatin_is_tested_not_background():
    # Only a MEDICINE named atorvastatin is the background line.
    key = record([fact("K1", "allergy", "atorvastatin")])
    parts = ssn.split_note(record([]), key)
    assert [f["fact_id"] for f in parts["tested"][1]["facts"]] == ["K1"]
    assert parts["background"][1]["facts"] == []


def test_split_note_keeps_all_fact_types_and_changes_nothing():
    tool = record([fact("T1", "diagnosis", "asthma"), fact("T2", "operation", "appendectomy"), atorva("T3")])
    parts = ssn.split_note(tool, record([]))
    assert [f["fact_id"] for f in parts["tested"][0]["facts"]] == ["T1", "T2"]
    assert len(tool["facts"]) == 3


def test_the_two_parts_add_up_to_the_whole_note():
    key = record([atorva("K1"), fact("K2", "allergy", "penicillin"), fact("K3", "medicine", "aspirin"),
                  fact("K4", "diagnosis", "asthma")])
    tool = record([atorva("T1", status="stopped"), fact("T2", "medicine", "aspirin", status="stopped"),
                   fact("T3", "allergy", "penicillin"), fact("T4", "allergy", "latex"), atorva("T5")])
    whole = score.score_patient(tool, key)["counts"]
    parts = ssn.split_note(tool, key)
    results = [score.score_patient(*parts[part]) for part in ssn.PARTS]
    for scope in score.SCOPES:
        for field in score.COUNT_FIELDS:
            assert sum(r["counts"][scope][field] for r in results) == whole[scope][field], (scope, field)


def test_note_is_right_only_with_no_missed_and_no_false_alarms():
    key = record([fact("K1", "allergy", "penicillin")])
    assert ssn.note_is_right(score.score_patient(record([fact("T1", "allergy", "penicillin")]), key))
    assert not ssn.note_is_right(score.score_patient(record([]), key))                         # missed
    assert not ssn.note_is_right(score.score_patient(
        record([fact("T1", "allergy", "penicillin"), fact("T2", "allergy", "latex")]), key))   # false alarm
    assert not ssn.note_is_right(score.score_patient(
        record([fact("T1", "allergy", "penicillin", status="suspected")]), key))                # wrong status
    # A trap note whose tested part is empty on the key side is right when the tool adds nothing.
    assert ssn.note_is_right(score.score_patient(record([]), record([])))
    assert not ssn.note_is_right(score.score_patient(record([fact("T1", "allergy", "penicillin")]), record([])))


def write_pairs(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ID", "trap_or_twin", "what_is_tested", "tested_fact", "background_fact"])
        writer.writerows(rows)


def test_load_pairs_follows_the_partner_named_in_the_text(tmp_path):
    path = tmp_path / "pairs.csv"
    write_pairs(path, [["D101", "trap", "Negation. Pair: D103", "", ""],
                       ["D102", "trap-control", "Control. Pair: D104", "", ""],
                       ["D103", "twin", "Plain. Pair: D101", "", ""],
                       ["D104", "twin-control", "Control twin. Pair: D102", "", ""]])
    notes, pairs = ssn.load_pairs(path)
    assert [(p["pair"], p["trap"]["ID"], p["twin"]["ID"]) for p in pairs] == [(1, "D101", "D103"), (2, "D102", "D104")]
    assert set(notes) == {"D101", "D102", "D103", "D104"}


def test_load_pairs_refuses_partners_that_do_not_point_at_each_other(tmp_path):
    path = tmp_path / "pairs.csv"
    write_pairs(path, [["D101", "trap", "Negation. Pair: D103", "", ""],
                       ["D102", "trap", "Other. Pair: D103", "", ""],
                       ["D103", "twin", "Plain. Pair: D101", "", ""]])
    with pytest.raises(ValueError):
        ssn.load_pairs(path)


def test_real_pairs_file_has_20_pairs_and_pair_9_is_d109_d129():
    notes, pairs = ssn.load_pairs(ssn.SETS["traps"]["pairs"])
    assert len(pairs) == 20 and len(notes) == 40
    assert set(notes) == set(ssn.SETS["traps"]["ids"])
    nine = next(p for p in pairs if p["pair"] == ssn.DOSE_CHANGE_PAIR)
    assert (nine["trap"]["ID"], nine["twin"]["ID"]) == ("D109", "D129")


def test_dose_change_note_reports_dose_history_and_flag_for_both_sides():
    def med(fact_id, dose, history, flags):
        f = fact(fact_id, "medicine", "amlodipine")
        f.update(dose=dose, history=history, flags=flags)
        return f
    old = [{"dose": "2.5 mg", "status": "current"}]
    key = record([med("K1", "5 mg", old, ["dose_changed"]), atorva("K2")])
    tool = record([med("T1", "5 mg", [{"dose": "2.5 mg", "status": "stopped"}], []), atorva("T2")])
    lines = ssn.dose_change_note(key, tool)
    assert len(lines) == 1           # the background line is not reported
    line = lines[0]
    assert "key dose 5 mg" in line and "tool dose 5 mg" in line
    assert "dose_changed yes; tool" in line and line.endswith("dose matches the key: yes")
    assert "dose_changed no;" in line
    # A tool with no fact of that name is said plainly.
    assert "no fact with this name" in ssn.dose_change_note(key, record([]))[0]


@pytest.mark.parametrize("pid", ["D001", "D100", "D141", "D201", "P021", "R001"])
def test_cli_traps_refuses_ids_outside_the_set_before_opening_anything(tmp_path, pid):
    with pytest.raises(SystemExit):
        ssn.main(["--set", "traps", "--patients", pid, "--out-dir", str(tmp_path / "out")])
    assert not (tmp_path / "out").exists()


def test_cli_traps_end_to_end_on_the_real_notes(tmp_path):
    out = tmp_path / "out"
    ssn.main(["--set", "traps", "--out-dir", str(out)])
    config = ssn.SETS["traps"]

    def read(name):
        with open(out / name, encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    assert len(read("per_note.csv")) == 40 and len(read("pairs.csv")) == 20
    # Tested + background add up to scoring each whole note with score.score_patient.
    whole = []
    for pid in config["ids"]:
        compiled = score.load_json(config["compiled_dir"] / f"{pid}.json")
        key = score.load_json(config["keys_dir"] / pid / f"{pid}_key.json")
        whole.append(score.score_patient(compiled, key))
    totals = score._sum_counts(whole)
    summary = read("summary.csv")
    for scope in score.SCOPES:
        for field in ("key_facts", "output_facts", "matched", "missed", "false_alarms", "wrong_status"):
            assert sum(int(r[field]) for r in summary if r["scope"] == scope) == totals[scope][field], (scope, field)
    # Every note's rightness in pairs.csv agrees with per_note.csv.
    right = {r["patient_id"]: r["tested_right"] for r in read("per_note.csv")}
    for row in read("pairs.csv"):
        assert row["trap_right"] == right[row["trap_id"]] and row["twin_right"] == right[row["twin_id"]]
    # Each failure row belongs to a note that is wrong, or to a background part.
    for row in read("failures.csv"):
        assert row["part"] in ssn.PARTS
        if row["part"] == "tested":
            assert right[row["patient_id"]] == "False"
