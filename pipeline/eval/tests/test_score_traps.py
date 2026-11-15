"""Tests for score_traps.py, the trap breakdown (T37). Run from the repo root:
    .venv/bin/python -m pytest pipeline/eval/tests

Every trap, key and record here is made up. No held-out file is opened.
"""

import csv
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL))

import score_traps as st  # noqa: E402


def fact(name, status="current", type_="medicine", dose=None):
    return {"type": type_, "name": name, "status": status, "dose": dose}


def trap(kind, name, answer, type_="medicine", pid="T0001"):
    return {"patient_id": pid, "trap": kind, "fact_type": type_, "fact_name": name,
            "hospitals": "A, B", "what_we_changed": "made up", "right_answer": answer}


SILENT = "{} still current, from Hospital B (silence is not a stop)"
STOP = "{}: stopped (2020-01-01, Hospital A); the earlier current entry in history"
ALLERGY = "{} allergy stays current (silence never removes an allergy), no conflict"


def test_expected_status_is_read_from_the_label_words():
    assert st.expected_status(STOP.format("x")) == "stopped"
    assert st.expected_status(SILENT.format("x")) == "current"
    assert st.expected_status("x 5 mg, current, flag dose_changed, 10 mg in history") == "current"
    assert st.expected_status(ALLERGY.format("x")) == "current"
    assert st.expected_status("allergy kept, in a conflict with Hospital A's 'no known allergies'") == "current"
    assert st.expected_status("something else") is None


def test_caught_when_the_record_has_the_keys_type_name_and_status():
    t = trap("silent_medicine", "drugx", SILENT.format("drugx"))
    outcomes, _ = st.score_trap(t, [fact("drugx"), fact("other")], {1: [fact("drugx")], 7: [fact("drugx"), fact("junk")]})
    assert outcomes == {1: "caught", 7: "caught"}


def test_not_caught_when_the_status_is_wrong_or_the_fact_is_missing():
    t = trap("stop_one_hospital", "drugx", STOP.format("drugx"))
    key = [fact("drugx", "stopped")]
    outcomes, detail = st.score_trap(t, key, {1: [fact("drugx", "current")], 7: []})
    assert outcomes == {1: "not_caught", 7: "not_caught"}
    assert detail["key_status"] == "stopped"


def test_name_match_ignores_case_and_type_must_match():
    t = trap("allergy_missed", "DrugX", ALLERGY.format("drugx"), type_="allergy")
    key = [fact("drugx", "current", "allergy")]
    outcomes, _ = st.score_trap(t, key, {1: [fact("drugx", "current", "medicine")], 7: [fact("DRUGX", "current", "allergy")]})
    assert outcomes == {1: "not_caught", 7: "caught"}


def test_label_overtaken_when_the_key_disagrees_with_the_label():
    # The label expects "stopped", but the key says "current": the label is out of date, not a miss.
    t = trap("stop_one_hospital", "drugx", STOP.format("drugx"))
    outcomes, detail = st.score_trap(t, [fact("drugx", "current")], {1: [], 7: [fact("drugx", "current")]})
    assert outcomes == {1: "label_overtaken", 7: "label_overtaken"}
    assert (detail["label_status"], detail["key_status"]) == ("stopped", "current")


def test_when_the_key_has_two_matching_facts_the_one_that_fits_the_label_is_used():
    t = trap("silent_medicine", "drugx", SILENT.format("drugx"))
    key = [fact("drugx", "stopped"), fact("drugx", "current")]
    outcomes, detail = st.score_trap(t, key, {7: [fact("drugx", "current")]})
    assert outcomes == {7: "caught"} and detail["key_matches"] == 2


def test_key_fact_not_found_is_reported_not_guessed():
    t = trap("silent_medicine", "drugx", SILENT.format("drugx"))
    outcomes, _ = st.score_trap(t, [fact("other")], {1: [fact("drugx")], 7: [fact("drugx")]})
    assert outcomes == {1: "key_fact_not_found", 7: "key_fact_not_found"}


def make_scored():
    traps = [
        trap("silent_medicine", "a", SILENT.format("a"), pid="T1"),
        trap("silent_medicine", "b", SILENT.format("b"), pid="T2"),
        trap("stop_one_hospital", "c", STOP.format("c"), pid="T3"),
        trap("stop_one_hospital", "d", STOP.format("d"), pid="T4"),
    ]
    keys = {"T1": [fact("a")], "T2": [fact("b")], "T3": [fact("c", "stopped")], "T4": [fact("d", "current")]}
    row1 = {"T1": [fact("a")], "T2": [], "T3": [fact("c", "current")], "T4": [fact("d")]}
    row7 = {"T1": [fact("a")], "T2": [fact("b")], "T3": [fact("c", "stopped")], "T4": [fact("d")]}
    return st.run(traps, [1, 7], key_for=lambda p: {"facts": keys[p]},
                  record_for=lambda r, p: {"facts": (row1 if r == 1 else row7)[p]})


def test_counts_per_type_and_row():
    by_type = st.count_by_type(make_scored(), [1, 7])
    pick = {(l["trap_type"], l["row"]): l for l in by_type}
    assert (pick["silent_medicine", 1]["caught"], pick["silent_medicine", 1]["not_caught"]) == (1, 1)
    assert (pick["silent_medicine", 7]["caught"], pick["silent_medicine", 7]["not_caught"]) == (2, 0)
    stop1 = pick["stop_one_hospital", 1]
    assert (stop1["caught"], stop1["not_caught"], stop1["label_overtaken"]) == (0, 1, 1)
    assert pick["stop_one_hospital", 7]["caught_of_scored"] == 1.0
    total7 = pick["all", 7]
    assert (total7["traps"], total7["caught"], total7["label_overtaken"]) == (4, 3, 1)


def test_output_files_split_ids_from_counts(tmp_path):
    detail, out = tmp_path / "detail", tmp_path / "out"
    st.write_outputs(make_scored(), [1, 7], detail, out)
    detail_text = (detail / "per_trap.csv").read_text(encoding="utf-8")
    counts_text = (out / "traps_by_type.csv").read_text(encoding="utf-8")
    assert "T1" in detail_text and "T3" in detail_text   # the detail file has the (made-up) IDs
    assert "T1" not in counts_text and "T3" not in counts_text
    assert not st.ID_SHAPE.search(counts_text)
    header = next(csv.reader(counts_text.splitlines()))
    assert header == st.TYPE_FIELDS
    assert "fact_name" not in header


def test_counts_file_refuses_text_that_looks_like_an_id(tmp_path, monkeypatch):
    monkeypatch.setitem(st.heldout_table.ROW_NAMES, 1, "P001 oops")
    with pytest.raises(st.TrapError):
        st.write_outputs(make_scored(), [1, 7], tmp_path / "d", tmp_path / "o")
    assert not (tmp_path / "o" / "traps_by_type.csv").exists()


def test_read_traps_stops_on_unreadable_label_or_unknown_patient(tmp_path):
    header = ["patient_id", "trap", "fact_type", "fact_name", "hospitals", "what_we_changed", "right_answer"]
    def write(name, rows):
        with open(tmp_path / name, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=header)
            writer.writeheader()
            writer.writerows(rows)
    good = trap("silent_medicine", "a", SILENT.format("a"), pid="T1")
    write("heldout_traps.csv", [good])
    write("reserve_traps.csv", [trap("silent_medicine", "b", "no idea", pid="T2")])
    with pytest.raises(st.TrapError, match="1 trap labels have no readable"):
        st.read_traps(tmp_path)
    write("reserve_traps.csv", [trap("silent_medicine", "b", SILENT.format("b"), pid="T2")])
    assert len(st.read_traps(tmp_path, expected_ids={"T1", "T2"})) == 2
    with pytest.raises(st.TrapError, match="1 trap patients are not held-out"):
        st.read_traps(tmp_path, expected_ids={"T1"})


# ---- dose_change traps: caught only with the key's dose and no other current fact with another dose ----
DOSE = "{} 10 mg, current, flag dose_changed, 5 mg in history"


def dose_trap(name="drugx"):
    return trap("dose_change", name, DOSE.format(name))


def dose_outcome(key_dose, out_facts, name="drugx"):
    outcomes, detail = st.score_trap(dose_trap(name), [fact(name, dose=key_dose)], {1: out_facts})
    return outcomes[1], detail["loose"][1], detail["dose_check"][1]


def test_dose_change_caught_with_the_keys_dose():
    assert dose_outcome("10 mg", [fact("drugx", dose="10 mg")]) == ("caught", True, "ok")


def test_dose_change_one_gram_equals_1000_mg():
    assert dose_outcome("1 g", [fact("drugx", dose="1000 mg")]) == ("caught", True, "ok")


def test_dose_change_wrong_dose_is_not_caught_but_still_counts_in_the_first_rule():
    assert dose_outcome("10 mg", [fact("drugx", dose="5 mg")]) == ("not_caught", True, "wrong_dose")
    assert dose_outcome("10 mg", [fact("drugx", dose=None)]) == ("not_caught", True, "wrong_dose")


def test_dose_change_not_caught_when_another_current_fact_has_a_different_dose():
    both = [fact("drugx", dose="5 mg"), fact("drugx", dose="10 mg")]
    assert dose_outcome("10 mg", both) == ("not_caught", True, "other_current_dose")


def test_dose_change_other_fact_with_no_dose_also_counts_as_a_different_dose():
    assert dose_outcome("10 mg", [fact("drugx", dose="10 mg"), fact("drugx", dose=None)])[0] == "not_caught"


def test_dose_change_a_stopped_or_second_copy_with_the_same_dose_does_not_spoil_it():
    out = [fact("drugx", dose="10 mg"), fact("drugx", "stopped", dose="5 mg"), fact("drugx", dose="10 mg")]
    assert dose_outcome("10 mg", out) == ("caught", True, "ok")
    assert dose_outcome("10 mg", [fact("drugx", dose="10 mg"), fact("othermed", dose="99 mg")])[0] == "caught"


def test_dose_change_missing_fact_fails_both_rules():
    assert dose_outcome("10 mg", []) == ("not_caught", False, "")


def test_dose_change_not_applicable_when_key_has_no_dose_or_is_a_combination():
    assert dose_outcome(None, [fact("drugx", dose="5 mg")]) == ("caught", True, "not_applicable")
    out, loose, check = dose_outcome("10 mg", [fact("a / b", dose="1 mg")], name="a / b")
    assert (out, loose, check) == ("caught", True, "not_applicable")


def test_other_trap_types_ignore_doses():
    t = trap("silent_medicine", "drugx", SILENT.format("drugx"))
    outcomes, detail = st.score_trap(t, [fact("drugx", dose="10 mg")],
                                     {1: [fact("drugx", dose="5 mg"), fact("drugx", dose="10 mg")]})
    assert outcomes == {1: "caught"} and detail["loose"] == {1: True} and detail["dose_check"] == {1: ""}


def test_both_caught_columns_are_counted_per_type():
    traps = [dose_trap("a"), dose_trap("b"), trap("silent_medicine", "c", SILENT.format("c"), pid="T3")]
    keys = {"a": "10 mg", "b": "10 mg"}
    for t, pid in zip(traps, ("T1", "T2", "T3")):
        t["patient_id"] = pid
    key_facts = {"T1": [fact("a", dose="10 mg")], "T2": [fact("b", dose="10 mg")], "T3": [fact("c")]}
    records = {"T1": [fact("a", dose="10 mg")],                          # right dose
               "T2": [fact("b", dose="5 mg"), fact("b", dose="10 mg")],  # two current doses
               "T3": [fact("c")]}
    scored = st.run(traps, [1], key_for=lambda p: {"facts": key_facts[p]}, record_for=lambda r, p: {"facts": records[p]})
    pick = {l["trap_type"]: l for l in st.count_by_type(scored, [1])}
    assert (pick["dose_change"]["caught"], pick["dose_change"]["caught_dose_not_checked"],
            pick["dose_change"]["not_caught"]) == (1, 2, 1)
    assert (pick["silent_medicine"]["caught"], pick["silent_medicine"]["caught_dose_not_checked"]) == (1, 1)
    assert (pick["all"]["caught"], pick["all"]["caught_dose_not_checked"]) == (2, 3)


# ---- refinement: an output fact that matches another key fact is not a stray extra ----
def two_entry_key():
    # The key itself holds two current entries of the same medicine with different doses.
    return [fact("drugx", dose="10 mg"), fact("drugx", dose="20 mg")]


def test_dose_change_two_key_entries_both_in_the_output_is_caught():
    outcomes, detail = st.score_trap(dose_trap(), two_entry_key(), {1: [fact("drugx", dose="20 mg"), fact("drugx", dose="10 mg")]})
    assert outcomes == {1: "caught"} and detail["dose_check"] == {1: "ok"}


def test_dose_change_a_real_stray_extra_is_still_caught_out_when_the_key_has_two_entries():
    out = [fact("drugx", dose="10 mg"), fact("drugx", dose="20 mg"), fact("drugx", dose="30 mg")]
    outcomes, detail = st.score_trap(dose_trap(), two_entry_key(), {1: out})
    assert outcomes == {1: "not_caught"} and detail["dose_check"] == {1: "other_current_dose"}


def test_dose_change_two_key_entries_but_only_the_other_dose_in_the_output():
    outcomes, detail = st.score_trap(dose_trap(), two_entry_key(), {1: [fact("drugx", dose="20 mg")]})
    assert outcomes == {1: "not_caught"} and detail["dose_check"] == {1: "wrong_dose"}


def test_dose_change_the_only_matching_output_is_taken_by_another_key_fact():
    # Trap key is the second entry (10 mg listed after a 5 mg one); the one output fact goes to the first entry.
    key = [fact("drugx", dose="5 mg"), fact("drugx", dose="10 mg")]
    t = dose_trap()
    key_for_trap = st.key_matches(t, key)[0]
    assert key_for_trap is key[0]  # key_matches returns the first, so the trap key is the 5 mg entry
    outcomes, detail = st.score_trap(t, key, {1: [fact("drugx", dose="10 mg")]})
    assert detail["dose_check"][1] in ("wrong_dose", "no_own_match") and outcomes == {1: "not_caught"}
