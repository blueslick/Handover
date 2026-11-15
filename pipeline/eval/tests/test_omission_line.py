"""Tests for omission_line.py (T37). Run from the repo root:
    .venv/bin/python -m pytest pipeline/eval/tests

Every flag, miss and name here is made up. No held-out file is opened.
"""

import csv
import json
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL))

import omission_line as ol  # noqa: E402


def write_omission(folder, records):
    folder.mkdir(parents=True)
    for name, pid, generics in records:
        flags = [{"flag": "possible_missed", "generic": g, "terms_as_written": [g], "lines": []} for g in generics]
        (folder / f"{name}.json").write_text(json.dumps({"patient_id": pid, "flags": flags}), encoding="utf-8")


def write_failures(folder, part, rows):
    (folder / part).mkdir(parents=True)
    with open(folder / part / "failures.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["patient_id", "kind", "name", "key_critical", "type"])
        writer.writeheader()
        writer.writerows(rows)


def test_counts_with_made_up_flags_and_misses(tmp_path):
    write_omission(tmp_path / "om", [
        ("T1_A", "T1", ["alpha"]),            # flag on a real miss (name absent)
        ("T1_B", "T1", []),
        ("T2_A", "T2", ["beta", "gamma"]),    # beta: on a wrong-status miss; gamma: not a miss
        ("T3_A", "T3", ["delta"]),            # not a miss
        ("T4_A", "T4", []),
    ])
    write_failures(tmp_path / "sc", "heldout", [
        {"patient_id": "T1", "kind": "missed", "name": "Alpha", "key_critical": "True", "type": "medicine"},
        {"patient_id": "T4", "kind": "missed", "name": "epsilon", "key_critical": "False", "type": "diagnosis"},   # no flag
        {"patient_id": "T2", "kind": "wrong_status", "name": "beta", "key_critical": "False", "type": "medicine"},
        {"patient_id": "T9", "kind": "false_alarm", "name": "zeta", "key_critical": "", "type": "medicine"},       # not a miss
    ])
    write_failures(tmp_path / "sc", "reserve", [])
    flags, records, with_flag = ol.read_flags(tmp_path / "om")
    misses = ol.read_misses(tmp_path / "sc")
    got = dict(ol.compute(flags, records, with_flag, misses, ({"alpha"}, {"alpha", "other"})))
    assert got["records_checked"] == 5 and got["records_with_a_flag"] == 3
    assert got["possible_missed_flags"] == 4 and got["patients_with_a_flag"] == 3
    assert got["row7_all_misses"] == 3 and got["row7_all_misses_pointed_at_by_a_flag"] == 2
    assert got["row7_name_absent_misses"] == 2 and got["row7_name_absent_misses_pointed_at_by_a_flag"] == 1
    assert got["row7_wrong_status_misses"] == 1 and got["row7_wrong_status_misses_pointed_at_by_a_flag"] == 1
    assert got["row7_critical_misses"] == 1 and got["row7_critical_misses_pointed_at_by_a_flag"] == 1
    assert got["flags_on_a_row7_miss"] == 2 and got["flags_not_on_a_row7_miss"] == 2
    # The two "name left out" misses: alpha (medicine, in both lists) and epsilon (diagnosis, in neither).
    assert (got["row7_name_absent_type_medicine"], got["row7_name_absent_type_diagnosis"]) == (1, 1)
    assert (got["row7_name_absent_type_allergy"], got["row7_name_absent_type_operation"]) == (0, 0)
    assert (got["row7_name_absent_in_drug_list"], got["row7_name_absent_in_brand_table"]) == (1, 1)
    assert (got["row7_name_absent_in_both_lists"], got["row7_name_absent_in_neither_list"]) == (1, 1)


def test_name_lists_read_both_columns_of_the_brand_table(tmp_path):
    (tmp_path / "drug_list.csv").write_text("name,kind\nAlpha,medicine\n", encoding="utf-8")
    (tmp_path / "brand_to_generic.csv").write_text("brand,generic\nBrandy,Gamma\n", encoding="utf-8")
    drugs, brands = ol.read_name_lists(tmp_path)
    assert drugs == {"alpha"} and brands == {"brandy", "gamma"}


def test_same_name_for_another_patient_does_not_count():
    got = dict(ol.compute([("T1", "alpha")], 1, 1, [("T2", "alpha", "missed", False, "medicine")]))
    assert got["row7_all_misses_pointed_at_by_a_flag"] == 0 and got["flags_not_on_a_row7_miss"] == 1


def test_output_file_has_counts_and_no_ids(tmp_path):
    lines = ol.compute([("T1", "alpha")], 1, 1, [("T1", "alpha", "missed", True, "medicine")])
    out = tmp_path / "omission_line.csv"
    ol.write_line(lines, out)
    text = out.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "measure,count"
    assert "T1" not in text and "alpha" not in text
