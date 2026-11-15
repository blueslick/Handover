"""Tests for cost_line.py (T37). Run from the repo root:
    .venv/bin/python -m pytest pipeline/eval/tests

Made-up usage files and made-up token counts. No real run is opened.
"""

import csv
import sys
from decimal import Decimal
from pathlib import Path

EVAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL))

import cost_line as cl  # noqa: E402


def write_usage(folder, calls):
    folder.mkdir(parents=True)
    with open(folder / "usage.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["patient_id", "hospital", "attempt", "input_tokens", "output_tokens"])
        writer.writeheader()
        writer.writerows(calls)


def call(pid, hospital, attempt, tokens_in, tokens_out):
    return {"patient_id": pid, "hospital": hospital, "attempt": attempt,
            "input_tokens": tokens_in, "output_tokens": tokens_out}


def test_usage_counts_calls_retries_tokens_and_patients(tmp_path):
    write_usage(tmp_path / "run", [call("T1", "A", 1, 1000, 200), call("T1", "B", 1, 3000, 400),
                                   call("T2", "A", 1, 2000, 300), call("T2", "A", 2, 2000, 350)])
    usage = cl.read_usage(tmp_path / "run" / "usage.csv")
    assert usage == {"calls": 4, "retries": 1, "input_tokens": 8000, "output_tokens": 1250, "patients": 2}


def test_cost_uses_the_price_per_million_and_divides_by_patients():
    usage = {"calls": 6, "retries": 0, "input_tokens": 1_000_000, "output_tokens": 500_000, "patients": 4}
    line = cl.cost_line(7, "Model X", "run", usage, Decimal("2"), Decimal("10"))
    assert line["input_cost_usd"] == Decimal("2.0000")      # 1M x $2
    assert line["output_cost_usd"] == Decimal("5.0000")     # 0.5M x $10
    assert line["total_cost_usd"] == Decimal("7.0000")      # the sum
    assert line["usd_per_patient"] == Decimal("1.75000")    # 7 / 4
    assert line["us_cents_per_patient"] == Decimal("175.000")


def test_output_file_has_totals_only(tmp_path):
    write_usage(tmp_path / "a", [call("T1", "A", 1, 1000, 100)])
    write_usage(tmp_path / "b", [call("T1", "A", 1, 1000, 100)])
    runs = {7: ("a", "Model X", Decimal("2"), Decimal("10")), 8: ("b", "Model Y", Decimal("0.1"), Decimal("0.5"))}
    lines = cl.build(tmp_path, runs)
    out = tmp_path / "cost.csv"
    cl.write_lines(lines, out)
    text = out.read_text(encoding="utf-8")
    assert text.splitlines()[0].split(",") == cl.FIELDS
    assert "T1" not in text
    assert len(text.splitlines()) == 3
