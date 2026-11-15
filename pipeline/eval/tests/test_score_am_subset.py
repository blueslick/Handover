"""Tests for score_am_subset.py (T76). Run from the repo root: .venv/bin/python -m pytest pipeline/eval/tests"""

import csv
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parents[1]
REPO = EVAL.parents[1]
sys.path.insert(0, str(EVAL))

import score_am_subset as sub  # noqa: E402


def test_filter_keeps_only_allergies_and_medicines():
    record = {"patient_id": "P001", "facts": [{"type": t} for t in ("allergy", "medicine", "diagnosis", "operation")]}
    assert [f["type"] for f in sub.filtered(record)["facts"]] == ["allergy", "medicine"]
    assert len(record["facts"]) == 4  # the original is not changed


# The full tool scored against itself-shaped files on one working patient: score.py's numbers come through.
def test_one_working_patient(tmp_path):
    out = tmp_path / "out"
    totals = tmp_path / "totals.csv"
    sub.main(["--out-root", str(out), "--totals-csv", str(totals),
              "--method", f"keyword={REPO / 'outputs' / 'baseline_keyword'}", "P001"])
    with totals.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [(r["method"], r["scope"]) for r in rows] == [("keyword", "all"), ("keyword", "critical")]
    assert "P001" not in totals.read_text(encoding="utf-8")
    assert (out / "keyword" / "summary.csv").exists()
