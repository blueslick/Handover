"""Tests for make_answer_key.py (T14). Run: python -m pytest pipeline/data/test_answer_key.py
or simply: python pipeline/data/test_answer_key.py

All test patients are made up here. No held-out file is read.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "shared"))
from make_answer_key import build_key, KeyError_  # noqa: E402
from validate import check_file  # noqa: E402

EXAMPLE = HERE.parent.parent / "shared" / "examples" / "compiled_example.json"


def fact(type_, name, status, date, quote, dose=None, freq=None, reaction=None, written=None):
    return {"type": type_, "name": name, "name_as_written": written if written is not None else name,
            "dose": dose, "frequency": freq, "reaction": reaction, "status": status,
            "date": date, "quote": quote, "flags": []}


def rec(pid, h, *facts):
    ext = "csv" if h == "A" else "txt"
    return {"hospital": h, "file": f"{pid}_{h}.{ext}", "facts": list(facts)}


def valid(key, tmp=Path("/tmp/_t14_key.json")):
    tmp.write_text(json.dumps(key))
    problems = check_file(tmp, "compiled")
    assert not problems, problems
    return key


def by_name(key, name):
    found = [f for f in key["facts"] if f["name"] == name]
    assert len(found) == 1, f"expected one {name} fact, got {len(found)}"
    return found[0]


def strip(f):
    return {k: v for k, v in f.items() if k not in ("fact_id", "conflict_group")}


# ------------------------------------------------------------------ demo patient

def demo_records():
    p = "D001"
    return [
        rec(p, "A",
            fact("allergy", None, "none_recorded", "2024-05-10", "NKDA", written=None),
            fact("medicine", "warfarin", "current", "2024-05-10", "Warfarin,3 mg,daily,current",
                 "3 mg", "daily", written="warfarin"),
            fact("medicine", "metformin", "current", "2024-05-10", "Metformin,500 mg,twice daily,current",
                 "500 mg", "twice_daily", written="metformin")),
        rec(p, "B",
            fact("allergy", "penicillin", "current", "2025-08-19", "Allergic to penicillin (rash).",
                 reaction="rash", written="Penicillin"),
            fact("medicine", "metformin", "current", "2025-08-19", "metformin increased to 1000 mg BD",
                 "1000 mg", "twice_daily")),
        rec(p, "C",
            fact("medicine", "warfarin", "stopped", "2026-03-02", "warfarin stopped two months ago"),
            fact("medicine", "paracetamol", "current", "2026-03-02", "Panadol 1 g PRN",
                 "1000 mg", "as_needed", written="Panadol")),
    ]


def test_demo_matches_shared_example():
    key = valid(build_key("D001", demo_records()))
    example = json.loads(EXAMPLE.read_text())
    mine = sorted((strip(f) for f in key["facts"]), key=lambda f: (f["type"], str(f["name"])))
    theirs = sorted((strip(f) for f in example["facts"]), key=lambda f: (f["type"], str(f["name"])))
    assert mine == theirs
    groups = {f["conflict_group"] for f in key["facts"] if f["type"] == "allergy"}
    assert groups == {"D001-C1"}


# ------------------------------------------------------------------ one test per rule

def test_rule1_same_drug_one_fact():
    p = "P901"
    key = valid(build_key(p, [
        rec(p, "A", fact("medicine", "amlodipine", "current", "2021-01-05", "a", "5 mg", "daily")),
        rec(p, "C", fact("medicine", "amlodipine", "current", "2021-06-01", "c", "5 mg", "daily",
                         written="Norvasc")),
    ]))
    f = by_name(key, "amlodipine")
    assert [s["hospital"] for s in f["sources"]] == ["A", "C"]
    assert f["hospital"] == "C" and f["name_as_written"] == "Norvasc" and f["history"] == []


def test_rule2_explicit_stop():
    p = "P902"
    key = valid(build_key(p, [
        rec(p, "A", fact("medicine", "warfarin", "current", "2020-01-01", "a", "3 mg", "daily")),
        rec(p, "B", fact("medicine", "warfarin", "stopped", "2021-01-01", "b")),
    ]))
    f = by_name(key, "warfarin")
    assert f["status"] == "stopped" and f["dose"] == "3 mg"
    assert [h["status"] for h in f["history"]] == ["current"]


def test_rule3_dose_change():
    p = "P903"
    key = valid(build_key(p, [
        rec(p, "A", fact("medicine", "metformin", "current", "2020-01-01", "a", "500 mg", "twice_daily")),
        rec(p, "B", fact("medicine", "metformin", "current", "2021-01-01", "b", "1000 mg", "twice_daily")),
    ]))
    f = by_name(key, "metformin")
    assert f["dose"] == "1000 mg" and "dose_changed" in f["flags"]
    assert f["history"][0]["dose"] == "500 mg"


def test_rule3_blank_dose_does_not_hide_a_change():
    p = "P904"
    key = valid(build_key(p, [
        rec(p, "A", fact("medicine", "metformin", "current", "2020-01-01", "a", "500 mg", "twice_daily")),
        rec(p, "B", fact("medicine", "metformin", "current", "2020-06-01", "b")),
        rec(p, "C", fact("medicine", "metformin", "current", "2021-01-01", "c", "1000 mg", "twice_daily")),
    ]))
    f = by_name(key, "metformin")
    assert f["dose"] == "1000 mg" and "dose_changed" in f["flags"]


def test_rule4_silence_is_not_a_stop():
    p = "P905"
    key = valid(build_key(p, [
        rec(p, "A", fact("medicine", "lisinopril", "current", "2020-01-01", "a", "10 mg", "daily")),
        rec(p, "B", fact("diagnosis", "hypertension", "current", "2021-01-01", "b")),
    ]))
    f = by_name(key, "lisinopril")
    assert f["status"] == "current" and f["hospital"] == "A" and f["date"] == "2020-01-01"


def test_rule5_allergy_vs_no_known_allergies():
    p = "P906"
    key = valid(build_key(p, [
        rec(p, "A", fact("allergy", "penicillin", "current", "2019-01-01", "a", reaction="rash")),
        rec(p, "B", fact("allergy", None, "none_recorded", "2021-01-01", "NKA")),
        rec(p, "C", fact("allergy", None, "none_recorded", "2021-02-01", "NKA")),
    ]))
    allergies = [f for f in key["facts"] if f["type"] == "allergy"]
    assert len(allergies) == 2  # penicillin + one "none" fact with two sources
    assert len({f["conflict_group"] for f in allergies}) == 1
    assert all("conflict" in f["flags"] for f in allergies)
    none = [f for f in allergies if f["status"] == "none_recorded"][0]
    assert len(none["sources"]) == 2


def test_rule6_same_day_disagreement_is_a_conflict():
    p = "P907"
    key = valid(build_key(p, [
        rec(p, "A", fact("medicine", "amlodipine", "current", "2021-01-01", "a", "5 mg", "daily")),
        rec(p, "B", fact("medicine", "amlodipine", "current", "2021-01-01", "b", "10 mg", "daily")),
    ]))
    amlo = [f for f in key["facts"] if f["name"] == "amlodipine"]
    assert len(amlo) == 2 and len({f["conflict_group"] for f in amlo}) == 1


def test_rule6_no_medicines_vs_current_medicine():
    p = "P908"
    key = valid(build_key(p, [
        rec(p, "A", fact("medicine", "amlodipine", "current", "2020-01-01", "a", "5 mg", "daily")),
        rec(p, "B", fact("medicine", None, "none_recorded", "2021-01-01", "No regular medicines")),
    ]))
    assert all("conflict" in f["flags"] for f in key["facts"])


def test_new_medicine_after_no_medicines_is_not_a_conflict():
    p = "P909"
    key = valid(build_key(p, [
        rec(p, "A", fact("medicine", None, "none_recorded", "2019-01-01", "No regular medicines")),
        rec(p, "B", fact("medicine", "amlodipine", "current", "2021-01-01", "b", "5 mg", "daily")),
    ]))
    assert not any(f["flags"] for f in key["facts"])


def test_combination_medicine_without_dose_gets_missing_dose():
    p = "P910"
    key = valid(build_key(p, [
        rec(p, "A", fact("medicine", "levonorgestrel / ethinyl estradiol", "current", "2021-01-01", "a")),
    ]))
    assert key["facts"][0]["flags"] == ["missing_dose"]


def test_bad_input_is_refused():
    p = "P911"
    for bad in (fact("medicine", "Amlodipine", "current", "2021-01-01", "a", "5 mg", "daily"),
                fact("medicine", "amlodipine", "current", None, "a", "5 mg", "daily")):
        try:
            build_key(p, [rec(p, "A", bad)])
        except KeyError_:
            continue
        raise AssertionError("bad input was accepted")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok  ", t.__name__)
    print(f"{len(tests)} tests passed")
