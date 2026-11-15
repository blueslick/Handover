"""Tests for the held-out mode of the eval scripts (T65). Run from the repo root:
    .venv/bin/python -m pytest pipeline/eval/tests

These tests never open a held-out file. Every case either stops before any held-out file would
be opened (and a trap fails the test if one would be) or only checks IDs, paths and counts.
"""

import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parents[1]
REPO = EVAL.parents[1]
sys.path.insert(0, str(EVAL))

import heldout_guard  # noqa: E402
import keyword_baseline as kb  # noqa: E402
import omission_check as oc  # noqa: E402
import rules_row  # noqa: E402
import score  # noqa: E402
import stack_rows  # noqa: E402

# A folder .gitignore covers. Tests only ask git about it; nothing is written here.
IGNORED = REPO / "outputs" / "results_heldout" / "guard_test_only"
# A folder git tracks: held-out output must never go here.
TRACKED = REPO / "outputs" / "results" / "guard_test_only"

# Every script that has a held-out mode: a name for the test report, its main(), and extra arguments.
SCRIPTS = [
    ("keyword_baseline", kb.main, []),
    ("rules_row", rules_row.main, []),
    ("omission_check", oc.main, ["--run-id", "20261115-v2-sonnet-5-5"]),
    ("stack_rows", stack_rows.main, ["--row", "5", "--run-id", "20261115-v2-sonnet-5-5"]),
]
try:
    import medspacy_baseline as mb  # noqa: E402
    SCRIPTS.append(("medspacy_baseline", mb.main, []))
except ImportError:  # medspacy is optional (not in requirements.txt)
    pass


@pytest.fixture(autouse=True)
def trap_any_held_out_read(monkeypatch):
    """Fail the test if any script gets as far as locating or reading a held-out record."""
    def trap(*args, **kwargs):
        raise AssertionError("a held-out file would have been opened")
    monkeypatch.setattr(heldout_guard, "patient_folder", trap)
    monkeypatch.setattr(stack_rows, "run_row", trap)
    monkeypatch.setattr(oc, "run_patient", trap)


def run_cli(main, argv, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["script.py"] + argv)
    main()


# --- Held-out IDs are refused without the flag ---------------------------------------------

@pytest.mark.parametrize("name,main,extra", SCRIPTS, ids=[s[0] for s in SCRIPTS])
@pytest.mark.parametrize("pid", ["P021", "R001"])
def test_heldout_refused_without_flag(name, main, extra, pid, monkeypatch, tmp_path):
    out = tmp_path / "out"
    with pytest.raises(SystemExit):
        run_cli(main, [pid, "--out-dir" if name != "omission_check" else "--out-root", str(out)] + extra, monkeypatch)
    assert not out.exists()


@pytest.mark.parametrize("name,main,extra", SCRIPTS, ids=[s[0] for s in SCRIPTS])
def test_all_heldout_needs_the_heldout_flag(name, main, extra, monkeypatch):
    with pytest.raises(SystemExit):
        run_cli(main, ["--all-heldout"] + extra, monkeypatch)


# --- With the flag, the freeze tag and a git-ignored folder are both needed -------------------

@pytest.mark.parametrize("name,main,extra", SCRIPTS, ids=[s[0] for s in SCRIPTS])
def test_heldout_refused_when_there_is_no_freeze_tag(name, main, extra, monkeypatch):
    monkeypatch.setattr(heldout_guard, "freeze_tag_exists", lambda: False)
    out_flag = "--out-root" if name == "omission_check" else "--out-dir"
    with pytest.raises(SystemExit) as stopped:
        run_cli(main, ["--heldout", "P021", out_flag, str(IGNORED)] + extra, monkeypatch)
    assert "freeze" in str(stopped.value)
    assert not IGNORED.exists()


@pytest.mark.parametrize("name,main,extra", SCRIPTS, ids=[s[0] for s in SCRIPTS])
@pytest.mark.parametrize("folder", [TRACKED, "outside"], ids=["tracked_folder", "outside_repo"])
def test_heldout_refused_when_output_folder_is_not_git_ignored(name, main, extra, folder, monkeypatch, tmp_path):
    monkeypatch.setattr(heldout_guard, "freeze_tag_exists", lambda: True)
    folder = tmp_path / "out" if folder == "outside" else folder
    out_flag = "--out-root" if name == "omission_check" else "--out-dir"
    with pytest.raises(SystemExit) as stopped:
        run_cli(main, ["--heldout", "P021", out_flag, str(folder)] + extra, monkeypatch)
    assert "git-ignored" in str(stopped.value)
    assert not folder.exists()


def test_the_guard_accepts_a_git_ignored_folder_once_the_tag_exists(monkeypatch):
    monkeypatch.setattr(heldout_guard, "freeze_tag_exists", lambda: True)
    heldout_guard.require_heldout_ok([IGNORED / "P021.json"])  # no error, nothing opened or written


def test_the_guard_checks_the_tag_before_the_folder(monkeypatch):
    monkeypatch.setattr(heldout_guard, "freeze_tag_exists", lambda: False)
    with pytest.raises(SystemExit) as stopped:
        heldout_guard.require_heldout_ok([TRACKED / "P021.json"])
    assert "freeze" in str(stopped.value)


def test_a_working_run_does_not_trigger_the_guard(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("the guard must not run for working patients")
    monkeypatch.setattr(heldout_guard, "require_heldout_ok", boom)
    assert heldout_guard.guard_run(["D001", "P001", "P020"], [TRACKED / "x.json"]) is False


# --- score.py: --include-heldout also needs the freeze tag ------------------------------------

def test_score_heldout_refused_when_there_is_no_freeze_tag(monkeypatch, tmp_path):
    monkeypatch.setattr(heldout_guard, "freeze_tag_exists", lambda: False)
    with pytest.raises(SystemExit) as stopped:
        score.main(["--compiled-dir", str(tmp_path), "--keys-dir", str(tmp_path), "--patients", "P021",
                    "--include-heldout", "--out-dir", str(IGNORED)])
    assert "freeze" in str(stopped.value)
    assert not IGNORED.exists()


def test_score_heldout_still_refused_for_a_tracked_folder_with_the_tag(monkeypatch, tmp_path):
    monkeypatch.setattr(heldout_guard, "freeze_tag_exists", lambda: True)
    with pytest.raises(SystemExit) as stopped:
        score.main(["--compiled-dir", str(tmp_path), "--keys-dir", str(tmp_path), "--patients", "P021",
                    "--include-heldout", "--out-dir", str(TRACKED)])
    assert "git-ignored" in str(stopped.value)
    assert not TRACKED.exists()


# --- rules_row.py never runs on nothing --------------------------------------------------------

def test_rules_row_with_no_ids_is_an_error(monkeypatch):
    with pytest.raises(SystemExit):
        run_cli(rules_row.main, [], monkeypatch)


def test_rules_row_with_heldout_flag_but_no_ids_is_an_error(monkeypatch):
    with pytest.raises(SystemExit):
        run_cli(rules_row.main, ["--heldout"], monkeypatch)


# --- The ID lists and folders: counts and paths only --------------------------------------------

def test_there_are_160_distinct_heldout_ids_and_none_is_open():
    ids = heldout_guard.heldout_ids()
    assert len(ids) == 160 and len(set(ids)) == 160
    assert not set(ids) & set(heldout_guard.OPEN_IDS)
    assert sum(1 for pid in ids if pid.startswith("P")) == 80
    assert sum(1 for pid in ids if pid.startswith("R")) == 80


def test_each_kind_of_patient_maps_to_its_own_folder(monkeypatch):
    monkeypatch.undo()  # the trap in the autouse fixture replaces patient_folder; this test needs the real one
    assert heldout_guard.patient_folder("D001").parent.name == "demo"
    assert heldout_guard.patient_folder("P001").parent.name == "working"
    assert heldout_guard.patient_folder("P020").parent.name == "working"
    assert heldout_guard.patient_folder("P021").parent.name == "heldout"
    assert heldout_guard.patient_folder("R001").parent.name == "reserve"


def test_without_the_flag_the_keyword_baseline_output_is_unchanged(monkeypatch, tmp_path):
    monkeypatch.undo()  # this test reads D001 only, so the trap is not needed
    run_cli(kb.main, ["D001", "--out-dir", str(tmp_path)], monkeypatch)
    committed = (REPO / "outputs" / "baseline_keyword" / "D001.json").read_bytes()
    assert (tmp_path / "D001.json").read_bytes() == committed
