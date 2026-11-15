"""Tests for omission_check.py (T41). Run from the repo root: .venv/bin/python -m pytest pipeline/eval/tests

The Panadol test works on a copy of D001's saved hospital C extraction. The saved file itself
is only read, and the test checks that its hash is unchanged afterwards.
"""

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL))

import keyword_baseline as kb  # noqa: E402
import omission_check as oc  # noqa: E402

REPO = EVAL.parents[1]
RUN = "20261114-v1-sonnet-5-5"
REAL_EXTRACTION = REPO / "outputs" / "extracted" / RUN / "D001_C.json"

NAMES = kb.load_names()
PATTERN = kb.build_pattern(NAMES)


# Fingerprint a file, so a test can show that it was not changed.
def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# Copy D001's saved hospital C extraction into a temporary folder, then delete the Panadol
# (paracetamol) fact from the copy only. Returns the temporary extracted-root folder.
@pytest.fixture
def copy_without_panadol(tmp_path):
    root = tmp_path / "extracted"
    (root / RUN).mkdir(parents=True)
    copy = root / RUN / "D001_C.json"
    shutil.copyfile(REAL_EXTRACTION, copy)
    saved = json.loads(copy.read_text(encoding="utf-8"))
    kept = [f for f in saved["facts"] if f.get("name") != "paracetamol"]
    assert len(saved["facts"]) - len(kept) == 1, "expected exactly one paracetamol fact in D001_C"
    saved["facts"] = kept
    copy.write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")
    return root


# Test: with the Panadol fact removed from the copy, the check flags Panadol on the line it
# came from. The real saved extraction is not changed.
def test_panadol_removed_from_copy_is_flagged(tmp_path, copy_without_panadol):
    real_before = sha256(REAL_EXTRACTION)
    oc.run_patient("D001", RUN, copy_without_panadol, tmp_path / "omission", NAMES, PATTERN)
    out = json.loads((tmp_path / "omission" / RUN / "D001_C.json").read_text(encoding="utf-8"))
    flags = out["flags"]
    assert [f["generic"] for f in flags] == ["paracetamol"]
    assert flags[0]["flag"] == "possible_missed"
    assert flags[0]["terms_as_written"] == ["Panadol"]
    assert flags[0]["lines"] == [{"line": 19, "text": "2. Panadol 1 g PRN"}]
    assert sha256(REAL_EXTRACTION) == real_before


# Test: the real D001 hospital C extraction, unchanged, gives no flags. Hospitals A and B
# have no saved extraction yet, so they are reported as skipped and not guessed at.
def test_real_d001_has_no_flags_and_a_b_are_skipped(tmp_path):
    real_before = sha256(REAL_EXTRACTION)
    results = oc.run_patient("D001", RUN, REPO / "outputs" / "extracted", tmp_path / "omission", NAMES, PATTERN)
    by_hospital = {r["hospital"]: r for r in results}
    assert by_hospital["A"]["status"] == "skipped: no saved extraction"
    assert by_hospital["B"]["status"] == "skipped: no saved extraction"
    out = json.loads((tmp_path / "omission" / RUN / "D001_C.json").read_text(encoding="utf-8"))
    assert out["flags"] == []
    assert sha256(REAL_EXTRACTION) == real_before


# Test: with no extracted facts at all, the names in hospital A (CSV) and hospital B (note) are
# all found, each on the right line. Uses the real D001 source files, read only.
def test_names_found_in_hospital_a_and_b_text():
    paths = {p.stem.split("_")[-1]: p for p in kb.record_files("D001")}
    flags_a = oc.check_record(paths["A"].read_text(encoding="utf-8"), [], NAMES, PATTERN)
    flags_b = oc.check_record(paths["B"].read_text(encoding="utf-8"), [], NAMES, PATTERN)
    lines_a = {f["generic"]: [x["line"] for x in f["lines"]] for f in flags_a}
    lines_b = {f["generic"]: [x["line"] for x in f["lines"]] for f in flags_b}
    assert lines_a == {"penicillin": [2], "metformin": [5], "warfarin": [6]}
    assert lines_b == {"metformin": [15], "warfarin": [15]}


# Test: a brand name is converted to its generic name, and the longer brand wins over a shorter
# name that sits inside it (Tylenol with Codeine is not also read as codeine on its own).
def test_brand_becomes_generic_and_longest_match_wins():
    assert oc.names_in_line("2. Tylenol with Codeine 1 g", NAMES, PATTERN) == [
        ("Tylenol with Codeine", "paracetamol / codeine")
    ]
    assert oc.names_in_line("1. Glucophage XR 500 mg", NAMES, PATTERN) == [("Glucophage XR", "metformin")]


# Test: a name only matches as a whole word, so "eggs" does not count as "egg".
def test_names_do_not_match_inside_longer_words():
    assert oc.names_in_line("eggs on toast", NAMES, PATTERN) == []


# Test: held-out and reserve IDs are refused before any file is opened. The folders passed in
# do not exist, so a refusal (ValueError) shows the check stopped before reading anything.
@pytest.mark.parametrize("pid", ["P021", "P100", "R001", "R080", "D002"])
def test_held_out_and_reserve_ids_are_refused(tmp_path, pid):
    with pytest.raises(ValueError):
        oc.run_patient(pid, RUN, tmp_path / "does_not_exist", tmp_path / "out", NAMES, PATTERN)


# Test: the flag name is the one spelled in the team's fixed list.
def test_flag_name_matches_fixed_list():
    assert oc.FLAG == "possible_missed"
    assert oc.FLAG in oc.FIXED["flags"]
