"""Cost per patient for the held-out runs (T37): row 7 (Sonnet 5.5) and row 8 (Haiku 5.5).

Usage (from the repo root, with the project venv):
    .venv/bin/python pipeline/eval/cost_line.py

Reads the usage.csv that every extraction run saved (one line per model call, with the input and
output tokens from the API reply). It adds up every call, including the retries, multiplies by the
price per million tokens, and divides by the number of patients. It makes no model calls.

Prices are US$ per million tokens, given by Abby on 15 Nov 2026 from the official Claude pricing
docs. Haiku 5.5 uses the lower price because every call is under 100K tokens.
Writes outputs/results/heldout/cost_per_patient.csv: totals only, no patient IDs.
"""

import csv
import sys
from decimal import Decimal
from pathlib import Path

import heldout_table

REPO = Path(__file__).resolve().parents[2]
EXTRACTED = REPO / "outputs" / "extracted"
OUT_FILE = REPO / "outputs" / "results" / "heldout" / "cost_per_patient.csv"

# row -> (run folder, model name, input price, output price), US$ per million tokens.
RUNS = {
    7: ("20261115-v2-heldout-sonnet-5-5", "Claude Sonnet 5.5", Decimal("2"), Decimal("10")),
    8: ("20261115-v2-heldout-haiku-5-5", "Claude Haiku 5.5", Decimal("0.10"), Decimal("0.50")),
}
MILLION = Decimal(1_000_000)
FIELDS = ["row", "model", "run_id", "patients", "calls", "retries", "input_tokens", "output_tokens",
          "input_usd_per_million", "output_usd_per_million", "input_cost_usd", "output_cost_usd",
          "total_cost_usd", "usd_per_patient", "us_cents_per_patient"]


# Add up one run's usage.csv: calls, retries (attempt 2), tokens and different patients.
def read_usage(path):
    calls = retries = tokens_in = tokens_out = 0
    patients = set()
    with open(path, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            calls += 1
            retries += row["attempt"] != "1"
            tokens_in += int(row["input_tokens"])
            tokens_out += int(row["output_tokens"])
            patients.add(row["patient_id"])
    return {"calls": calls, "retries": retries, "input_tokens": tokens_in,
            "output_tokens": tokens_out, "patients": len(patients)}


# Turn token totals into dollars. Decimal, so the sums are exact.
def cost_line(row, model, run_id, usage, price_in, price_out):
    cost_in = Decimal(usage["input_tokens"]) * price_in / MILLION
    cost_out = Decimal(usage["output_tokens"]) * price_out / MILLION
    total = cost_in + cost_out
    per_patient = total / usage["patients"]
    return {
        "row": row, "model": model, "run_id": run_id, **usage,
        "input_usd_per_million": price_in, "output_usd_per_million": price_out,
        "input_cost_usd": round(cost_in, 4), "output_cost_usd": round(cost_out, 4),
        "total_cost_usd": round(total, 4), "usd_per_patient": round(per_patient, 5),
        "us_cents_per_patient": round(per_patient * 100, 3),
    }


def build(extracted_root, runs=RUNS):
    return [cost_line(row, model, run_id, read_usage(Path(extracted_root) / run_id / "usage.csv"), p_in, p_out)
            for row, (run_id, model, p_in, p_out) in runs.items()]


def write_lines(lines, out_file):
    out_file = Path(out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(lines)


def main():
    lines = build(EXTRACTED)
    write_lines(lines, OUT_FILE)
    for line in lines:
        print(f"Row {line['row']} ({line['model']}): {line['calls']} calls, {line['retries']} retries, "
              f"{line['patients']} patients")
        print(f"   input  {line['input_tokens']:,} tokens x ${line['input_usd_per_million']}/M = ${line['input_cost_usd']}")
        print(f"   output {line['output_tokens']:,} tokens x ${line['output_usd_per_million']}/M = ${line['output_cost_usd']}")
        print(f"   sum    ${line['total_cost_usd']} for {line['patients']} patients "
              f"= ${line['usd_per_patient']} per patient ({line['us_cents_per_patient']} US cents)")
    print(f"Wrote {OUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
