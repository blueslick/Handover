"""Tests for score.py (T18). Run from the repo root: .venv/bin/python -m pytest pipeline/eval/tests

Uses only the demo patient D001 and small made-up records. It never opens a held-out file.
"""

import csv
import json
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parents[1]
REPO = EVAL.parents[1]
sys.path.insert(0, str(EVAL))

import score  # noqa: E402

SAMPLE = REPO / "shared" / "sample" / "D001_compiled.json"
D001_KEY = REPO / "pipeline" / "data" / "demo" / "D001" / "D001_key.json"
D001_BASELINE = REPO / "outputs" / "baseline_keyword" / "D001.json"


def load(path):
    """Read a JSON file as UTF-8."""
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def fact(type_, name, status, n=1, **extra):
    """Build a made-up compiled fact with only the fields scoring reads, plus any extras."""
    base = {
        "fact_id": f"P099-F{n:02d}", "patient_id": "P099", "type": type_, "name": name,
        "name_as_written": name, "dose": None, "frequency": None, "reaction": None,
        "status": status, "hospital": "A", "date": "2021-01-01", "quote": f"quote for {name}",
        "sources": [], "history": [], "flags": [], "conflict_group": None,
    }
    base.update(extra)
    return base


def record(facts, patient_id="P099"):
    """Wrap facts in the compiled-record shape."""
    return {"format_version": "1.0", "kind": "compiled", "patient_id": patient_id,
            "run_id": None, "built_from": ["P099_A.csv"], "facts": facts}


def all_counts(result):
    """The counts over all facts."""
    return result["counts"]["all"]


def crit_counts(result):
    """The counts over critical facts only."""
    return result["counts"]["critical"]


# --- Real data -----------------------------------------------------------------------------

def test_d001_sample_against_key_is_perfect():
    # The hand-written sample should match the D001 answer key exactly.
    result = score.score_patient(load(SAMPLE), load(D001_KEY))
    counts = all_counts(result)
    assert counts["key_facts"] == 7
    assert counts["matched"] == 7
    assert counts["missed"] == 0
    assert counts["false_alarms"] == 0
    assert counts["wrong_status"] == 0
    assert counts["duplicates"] == 0
    assert counts["conflict_facts"] == 2
    assert counts["conflict_shown"] == 2
    assert result["problems"] == []
    assert crit_counts(result)["missed"] == 0
    assert crit_counts(result)["false_alarms"] == 0


@pytest.mark.skipif(not D001_BASELINE.exists(), reason="D001 keyword baseline not written yet")
def test_d001_keyword_baseline_has_warfarin_wrong_status():
    # The keyword baseline says warfarin is current; the key says it was stopped.
    result = score.score_patient(load(D001_BASELINE), load(D001_KEY))
    wrong = [p for p in result["problems"] if p["kind"] == "wrong_status"]
    assert len(wrong) == 1
    assert wrong[0]["name"] == "warfarin"
    assert wrong[0]["key_status"] == "stopped"
    assert wrong[0]["output_status"] == "current"
    assert wrong[0]["output_quote"]

    # The full counts, worked out by hand from the two files.
    counts = all_counts(result)
    assert (counts["key_facts"], counts["output_facts"]) == (7, 7)
    assert counts["matched"] == 3          # penicillin, metformin 1000 mg, paracetamol
    assert counts["missed"] == 4           # NKA, warfarin (wrong status), atrial fibrillation, type 2 diabetes
    assert counts["wrong_status"] == 1
    assert counts["duplicates"] == 2       # two extra metformin "current" facts
    assert counts["false_alarms"] == 4     # the wrong-status fact, two duplicates, one plain extra warfarin
    assert counts["dose_correct"] == 2     # metformin 1000 mg; paracetamol "1 g" is 1000 mg
    assert counts["dose_wrong"] == 0
    assert counts["conflict_facts"] == 2
    assert counts["conflict_shown"] == 0   # the baseline shows no conflict
    crit = crit_counts(result)
    assert crit["key_facts"] == 4          # 2 allergies + 2 current medicines
    assert crit["matched"] == 3
    assert crit["missed"] == 1             # the NKA allergy; warfarin is not critical on the key side


# --- Matching rules ------------------------------------------------------------------------

def test_name_match_ignores_case():
    key = {"patient_id": "P099", "facts": [fact("medicine", "warfarin", "current", dose="5 mg")]}
    out = record([fact("medicine", "Warfarin", "current", dose="5 mg")])
    counts = all_counts(score.score_patient(out, key))
    assert counts["matched"] == 1
    assert counts["missed"] == 0


def test_each_key_fact_matches_at_most_one_output():
    # Two identical key facts, one output fact: one matched, one missed.
    key = {"patient_id": "P099", "facts": [
        fact("diagnosis", "asthma", "current", n=1), fact("diagnosis", "asthma", "current", n=2)]}
    out = record([fact("diagnosis", "asthma", "current")])
    counts = all_counts(score.score_patient(out, key))
    assert counts["matched"] == 1
    assert counts["missed"] == 1


def test_extra_output_with_same_status_is_a_duplicate_and_a_false_alarm():
    key = {"patient_id": "P099", "facts": [fact("medicine", "metformin", "current", dose="1000 mg")]}
    out = record([
        fact("medicine", "metformin", "current", n=1, dose="1000 mg"),
        fact("medicine", "metformin", "current", n=2, dose="500 mg"),
    ])
    result = score.score_patient(out, key)
    counts = all_counts(result)
    assert counts["matched"] == 1
    assert counts["duplicates"] == 1
    assert counts["false_alarms"] == 1
    assert counts["wrong_status"] == 0
    assert [p["kind"] for p in result["problems"]] == ["false_alarm"]
    assert result["problems"][0]["duplicate"] is True


def test_wrong_status_is_one_missed_and_one_false_alarm():
    key = {"patient_id": "P099", "facts": [fact("medicine", "warfarin", "stopped", dose="5 mg")]}
    out = record([fact("medicine", "warfarin", "current", dose="5 mg")])
    result = score.score_patient(out, key)
    counts = all_counts(result)
    assert counts["matched"] == 0
    assert counts["missed"] == 1
    assert counts["false_alarms"] == 1
    assert counts["wrong_status"] == 1
    assert counts["duplicates"] == 0
    assert [p["kind"] for p in result["problems"]] == ["wrong_status"]


def test_failure_rows_name_key_and_output_fact_ids_separately():
    # A wrong status has both sides; a missed case has only the key side; a false alarm has only the output side.
    key = {"patient_id": "P099", "facts": [
        fact("medicine", "warfarin", "stopped", n=1, dose="5 mg"),
        fact("allergy", "penicillin", "current", n=2),
    ]}
    out = record([
        fact("medicine", "warfarin", "current", n=7, dose="5 mg"),
        fact("medicine", "aspirin", "current", n=8),
    ])
    result = score.score_patient(out, key)
    by_kind = {p["kind"]: p for p in result["problems"]}

    wrong = score._problem("P099", "wrong_status", key=key["facts"][0], out=out["facts"][0])
    assert (wrong["key_fact_id"], wrong["output_fact_id"]) == ("P099-F01", "P099-F07")
    assert "fact_id" not in wrong
    assert by_kind["wrong_status"]["key_fact_id"] == "P099-F01"
    assert by_kind["wrong_status"]["output_fact_id"] == "P099-F07"

    assert by_kind["missed"]["key_fact_id"] == "P099-F02"
    assert by_kind["missed"]["output_fact_id"] is None

    assert by_kind["false_alarm"]["key_fact_id"] is None
    assert by_kind["false_alarm"]["output_fact_id"] == "P099-F08"


def test_critical_split_uses_each_facts_own_criticality():
    # A stopped medicine that is missed is not critical; a current medicine that is missed is.
    key = {"patient_id": "P099", "facts": [
        fact("medicine", "aspirin", "stopped", n=1, dose="75 mg"),
        fact("medicine", "ramipril", "current", n=2, dose="5 mg"),
    ]}
    counts = all_counts(score.score_patient(record([]), key))
    assert counts["missed"] == 2
    crit = crit_counts(score.score_patient(record([]), key))
    assert crit["missed"] == 1
    assert crit["key_facts"] == 1


# --- Doses ---------------------------------------------------------------------------------

def test_dose_grams_are_compared_as_milligrams():
    key = {"patient_id": "P099", "facts": [fact("medicine", "paracetamol", "current", dose="1000 mg")]}
    out = record([fact("medicine", "paracetamol", "current", dose="1 g")])
    counts = all_counts(score.score_patient(out, key))
    assert counts["dose_correct"] == 1
    assert counts["dose_wrong"] == 0


def test_wrong_dose_counts_as_dose_wrong():
    key = {"patient_id": "P099", "facts": [fact("medicine", "metformin", "current", dose="1000 mg")]}
    out = record([fact("medicine", "metformin", "current", dose="500 mg")])
    counts = all_counts(score.score_patient(out, key))
    assert counts["matched"] == 1
    assert counts["dose_wrong"] == 1


def test_key_without_dose_is_not_applicable():
    key = {"patient_id": "P099", "facts": [fact("medicine", "vitamin d", "current", dose=None)]}
    out = record([fact("medicine", "vitamin d", "current", dose="800 units")])
    counts = all_counts(score.score_patient(out, key))
    assert counts["dose_not_applicable"] == 1
    assert counts["dose_correct"] == 0
    assert counts["dose_wrong"] == 0


# --- Conflicts -----------------------------------------------------------------------------

def _conflict_key():
    """A key with two sides of one conflict: penicillin allergy against no known allergies."""
    return {"patient_id": "P099", "facts": [
        fact("allergy", "penicillin", "current", n=1, reaction="rash", flags=["conflict"], conflict_group="P099-C1"),
        fact("allergy", None, "none_recorded", n=2, flags=["conflict"], conflict_group="P099-C1"),
    ]}


def test_conflict_shown_needs_both_sides_flagged():
    key = _conflict_key()
    both = record([
        fact("allergy", "penicillin", "current", n=1, flags=["conflict"], conflict_group="P099-C1"),
        fact("allergy", None, "none_recorded", n=2, flags=["conflict"], conflict_group="P099-C1"),
    ])
    counts = all_counts(score.score_patient(both, key))
    assert counts["conflict_facts"] == 2
    assert counts["conflict_shown"] == 2


def test_conflict_not_shown_when_one_side_missing_or_unflagged():
    key = _conflict_key()
    one_side = record([
        fact("allergy", "penicillin", "current", n=1, flags=["conflict"], conflict_group="P099-C1"),
    ])
    counts = all_counts(score.score_patient(one_side, key))
    assert counts["conflict_facts"] == 2
    assert counts["conflict_shown"] == 0

    no_flag = record([
        fact("allergy", "penicillin", "current", n=1),
        fact("allergy", None, "none_recorded", n=2, flags=["conflict"], conflict_group="P099-C1"),
    ])
    counts = all_counts(score.score_patient(no_flag, key))
    assert counts["conflict_shown"] == 0


# --- Command line -------------------------------------------------------------------------

def test_cli_refuses_held_out_id_before_opening_anything(tmp_path):
    # P021 is held-out: the script must stop without reading any file.
    with pytest.raises(SystemExit):
        score.main(["--compiled-dir", str(tmp_path), "--keys-dir", str(tmp_path),
                    "--patients", "P021", "--out-dir", str(tmp_path / "out")])
    assert not (tmp_path / "out").exists()


def test_cli_writes_csv_files_for_d001(tmp_path):
    # Copy the sample in as D001.json and score it against the demo key folder.
    compiled_dir = tmp_path / "compiled"
    compiled_dir.mkdir()
    (compiled_dir / "D001.json").write_text(SAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    out_dir = tmp_path / "out"

    score.main(["--compiled-dir", str(compiled_dir), "--keys-dir", str(REPO / "pipeline" / "data" / "demo"),
                "--patients", "D001", "--out-dir", str(out_dir)])

    with open(out_dir / "per_patient.csv", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    row = rows[0]
    assert row["patient_id"] == "D001"
    assert row["age_band"] == ""           # the demo patient is not in patients.csv
    assert row["missed_all"] == "0"
    assert row["false_alarms_all"] == "0"
    assert row["matched_all"] == "7"
    assert row["matched_critical"] == "4"

    with open(out_dir / "summary.csv", encoding="utf-8", newline="") as handle:
        summary = {r["scope"]: r for r in csv.DictReader(handle)}
    assert summary["all"]["recall"] == "1.0"
    assert summary["all"]["precision"] == "1.0"
    assert (out_dir / "failures.csv").exists()


def test_cli_failures_csv_has_separate_key_and_output_fact_id_columns(tmp_path):
    # The D001 keyword baseline has a real wrong-status case (warfarin), so both ID columns get checked.
    compiled_dir = tmp_path / "compiled"
    compiled_dir.mkdir()
    (compiled_dir / "D001.json").write_text(D001_BASELINE.read_text(encoding="utf-8"), encoding="utf-8")
    out_dir = tmp_path / "out"

    score.main(["--compiled-dir", str(compiled_dir), "--keys-dir", str(REPO / "pipeline" / "data" / "demo"),
                "--patients", "D001", "--out-dir", str(out_dir)])

    with open(out_dir / "failures.csv", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames
        rows = list(reader)
    assert "fact_id" not in header
    assert "key_fact_id" in header and "output_fact_id" in header

    wrong = [r for r in rows if r["kind"] == "wrong_status"]
    assert len(wrong) >= 1
    assert all(r["key_fact_id"] and r["output_fact_id"] for r in wrong)
    # A false alarm has no key fact, and a missed case has no output fact, so those cells are blank.
    assert all(r["key_fact_id"] == "" for r in rows if r["kind"] == "false_alarm")
    assert all(r["output_fact_id"] == "" for r in rows if r["kind"] == "missed")


# --- Held-out output must be git-ignored -----------------------------------------------------

def test_heldout_output_refused_in_tracked_folder(tmp_path):
    # outputs/ is tracked by git, so held-out scores must not be written there.
    tracked = REPO / "outputs" / "results" / "should_not_exist"
    with pytest.raises(SystemExit):
        score._check_heldout_output(tracked)
    assert not tracked.exists()


def test_heldout_output_refused_outside_repo(tmp_path):
    # A folder outside the repo cannot be checked by git, so it is refused (fails closed).
    with pytest.raises(SystemExit):
        score._check_heldout_output(tmp_path / "out")


def test_heldout_output_accepted_in_git_ignored_folder():
    # pipeline/data/synthea_raw/ is ignored by .gitignore. Nothing is written here by the test.
    score._check_heldout_output(REPO / "pipeline" / "data" / "synthea_raw" / "heldout_check_only")


def test_cli_heldout_run_refused_before_reading_when_out_dir_is_tracked(tmp_path):
    # P021 is held-out. With --include-heldout but a tracked output folder, nothing is read or written.
    tracked = REPO / "outputs" / "results" / "should_not_exist"
    with pytest.raises(SystemExit):
        score.main(["--compiled-dir", str(tmp_path), "--keys-dir", str(tmp_path), "--patients", "P021",
                    "--include-heldout", "--out-dir", str(tracked)])
    assert not tracked.exists()


# --- Combination medicines (T12): never dose-scored --------------------------------------

COMBO = "levonorgestrel / ethinyl estradiol"


def test_combination_key_without_dose_is_not_applicable():
    # The normal case: combinations have no dose in the key, so they are not dose-scored.
    key = {"patient_id": "P099", "facts": [fact("medicine", COMBO, "current", dose=None)]}
    out = record([fact("medicine", COMBO, "current", dose="150 mcg")])
    result = score.score_patient(out, key)
    counts = all_counts(result)
    assert counts["matched"] == 1
    assert counts["dose_not_applicable"] == 1
    assert counts["dose_correct"] == 0
    assert counts["dose_wrong"] == 0
    assert counts["combination_keys_with_dose"] == 0
    assert result["warnings"] == []


def test_combination_key_with_dose_is_not_applicable_and_warns():
    # A bad key dose on a combination: not dose-scored, so no score changes, but it is warned and counted.
    key = {"patient_id": "P099", "facts": [fact("medicine", COMBO, "current", dose="150 mcg")]}
    for out_dose in ("150 mcg", "300 mcg"):
        out = record([fact("medicine", COMBO, "current", dose=out_dose)])
        result = score.score_patient(out, key)
        counts = all_counts(result)
        assert counts["matched"] == 1
        assert counts["dose_not_applicable"] == 1
        assert counts["dose_correct"] == 0
        assert counts["dose_wrong"] == 0
        assert counts["combination_keys_with_dose"] == 1
        assert crit_counts(result)["combination_keys_with_dose"] == 1
        assert len(result["warnings"]) == 1
        warning = result["warnings"][0]
        assert warning["patient_id"] == "P099"
        assert warning["fact_id"] == "P099-F01"
        assert "P099-F01" in warning["message"]


def test_single_drug_key_is_still_dose_scored():
    # Single-drug medicines are unchanged: a correct dose scores as dose_correct, with no warning.
    key = {"patient_id": "P099", "facts": [fact("medicine", "metformin", "current", dose="1000 mg")]}
    out = record([fact("medicine", "metformin", "current", dose="1 g")])
    result = score.score_patient(out, key)
    counts = all_counts(result)
    assert counts["dose_correct"] == 1
    assert counts["dose_not_applicable"] == 0
    assert counts["combination_keys_with_dose"] == 0
    assert result["warnings"] == []


def test_cli_prints_combination_warning_and_counts_it(tmp_path, capsys):
    # The command line prints the warning (patient and fact ID only) and counts it in summary.csv.
    combo_fact = fact("medicine", COMBO, "current", dose="150 mcg", fact_id="D001-F01")
    keys_dir = tmp_path / "keys"
    (keys_dir / "D001").mkdir(parents=True)
    compiled_dir = tmp_path / "compiled"
    compiled_dir.mkdir()
    key = {"format_version": "1.0", "kind": "answer_key", "patient_id": "D001", "run_id": None,
           "built_from": ["D001_A.csv"], "facts": [combo_fact]}
    compiled = dict(key, kind="compiled", facts=[dict(combo_fact)])
    (keys_dir / "D001" / "D001_key.json").write_text(json.dumps(key), encoding="utf-8")
    (compiled_dir / "D001.json").write_text(json.dumps(compiled), encoding="utf-8")
    out_dir = tmp_path / "out"

    score.main(["--compiled-dir", str(compiled_dir), "--keys-dir", str(keys_dir),
                "--patients", "D001", "--out-dir", str(out_dir)])

    err = capsys.readouterr().err
    assert "D001" in err and "D001-F01" in err
    assert "combination medicine" in err
    with open(out_dir / "summary.csv", encoding="utf-8", newline="") as handle:
        summary = {r["scope"]: r for r in csv.DictReader(handle)}
    assert summary["all"]["combination_keys_with_dose"] == "1"
