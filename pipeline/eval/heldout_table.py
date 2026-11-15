"""Held-out build-up table (T37): add up the held-out scores for rows 1 to 8.

Usage (from the repo root, with the project venv):
    .venv/bin/python pipeline/eval/heldout_table.py

Reads, for each row N, the two per_patient.csv files that score.py wrote
(outputs/results_heldout/scores/row<N>/heldout/ and .../reserve/). Those folders are
git-ignored and hold patient IDs. This script never writes an ID or a quote. It makes no
model calls and does not change any score.

What it does, for each row:
1. Checks there are exactly 160 different patients, and exactly 20 in each of the 8 age-sex
   groups (age bands 0-19, 20-44, 45-64, 65+, times F and M). If not, it stops with counts only.
2. Adds up the counts of all 160 patients. It does not average the two summary.csv files.
3. Works out recall and precision from the totals, the same way score.py does
   (recall = matched / key facts, precision = matched / output facts).

Writes, for all facts and for critical facts only (allergies and current medicines):
    outputs/results/heldout/buildup_table.csv   one line per row and scope
    outputs/results/heldout/by_age_sex.csv      the chosen rows (default 1 and 7) per group
Both files hold totals only, so they are safe to commit. The script checks its own output for
anything shaped like a patient ID before it writes.
"""

import argparse
import csv
import re
import sys
from io import StringIO
from pathlib import Path

import heldout_guard
import score  # COUNT_FIELDS, SCOPES and _ratio: the same definitions as the scoring itself

REPO = Path(__file__).resolve().parents[2]
SCORES_ROOT = REPO / "outputs" / "results_heldout" / "scores"
OUT_DIR = REPO / "outputs" / "results" / "heldout"

# One name per build-up row: exactly the method names in app/data/results.json (Theo's How we tested tab).
ROW_NAMES = {
    1: "Keyword search, stack everything",
    2: "medSpaCy, stack everything",
    3: "Keyword search + six merge rules",
    4: "Claude, plain lists, stack everything",
    5: "Claude, status labels, stack everything",
    6: "Claude, status labels + Check, stack everything",
    7: "Claude, status labels + Check + six merge rules (the full tool)",
    8: "The full tool (row 7) on Claude Haiku 5.5, a cheaper second model, for comparison",
}
PARTS = ("heldout", "reserve")  # the two folders of answer keys, so two scoring runs per row

AGE_BANDS = ("0-19", "20-44", "45-64", "65+")
SEXES = ("F", "M")
GROUPS = [(age, sex) for age in AGE_BANDS for sex in SEXES]
N_PATIENTS = 160
PER_GROUP = 20

# The columns of both output files, after the labels. Counts first, then the two rates.
TABLE_COUNTS = [
    "key_facts", "output_facts", "matched", "missed", "false_alarms", "wrong_status",
    "duplicates", "dose_correct", "dose_wrong", "dose_not_applicable",
    "conflict_shown", "conflict_facts",
]
# Anything shaped like a patient ID. The output files must not contain one.
ID_SHAPE = re.compile(r"\b[PRD]\d{3}\b")


class TableError(Exception):
    """A check failed. The message gives counts only, never a patient ID."""


# Read one per_patient.csv from score.py: every count column becomes a whole number.
def read_per_patient(path):
    with open(path, encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for field in score.COUNT_FIELDS:
            for scope in score.SCOPES:
                row[f"{field}_{scope}"] = int(row[f"{field}_{scope}"])
    return rows


# Read both halves (heldout and reserve) of one row, from the scores folder.
def read_row(scores_root, row_number):
    rows = []
    for part in PARTS:
        path = Path(scores_root) / f"row{row_number}" / part / "per_patient.csv"
        if not path.exists():
            raise TableError(f"row {row_number}: {part} scores are missing (run score.py first)")
        rows.extend(read_per_patient(path))
    return rows


# Check one row has exactly 160 different patients, 20 in each age-sex group, and (when
# expected_ids is given) that they are exactly the held-out patients. Counts only in messages.
def check_row(rows, row_number, expected_ids=None):
    ids = [row["patient_id"] for row in rows]
    if len(ids) != N_PATIENTS or len(set(ids)) != N_PATIENTS:
        raise TableError(f"row {row_number}: {len(ids)} patient lines, {len(set(ids))} different "
                         f"(expected {N_PATIENTS} different)")
    if expected_ids is not None:
        missing, extra = len(set(expected_ids) - set(ids)), len(set(ids) - set(expected_ids))
        if missing or extra:
            raise TableError(f"row {row_number}: {missing} held-out patients missing, {extra} not held-out")
    sizes = {group: 0 for group in GROUPS}
    outside = 0
    for row in rows:
        group = (row["age_band"], row["sex"])
        if group in sizes:
            sizes[group] += 1
        else:
            outside += 1
    bad = {group: n for group, n in sizes.items() if n != PER_GROUP}
    if outside or bad:
        shown = ", ".join(f"{age}/{sex}: {n}" for (age, sex), n in bad.items())
        raise TableError(f"row {row_number}: {outside} patients outside the 8 groups; "
                         f"groups without exactly {PER_GROUP}: {shown or 'none'}")


# Add up the counts of many patients, for each scope. A plain sum, never an average.
def sum_counts(rows):
    totals = {scope: dict.fromkeys(score.COUNT_FIELDS, 0) for scope in score.SCOPES}
    for row in rows:
        for scope in score.SCOPES:
            for field in score.COUNT_FIELDS:
                totals[scope][field] += row[f"{field}_{scope}"]
    return totals


# One output line: labels, the counts, and recall and precision worked out as score.py does.
def make_line(labels, counts):
    line = dict(labels)
    for field in TABLE_COUNTS:
        line[field] = counts[field]
    line["recall"] = score._ratio(counts["matched"], counts["key_facts"])
    line["precision"] = score._ratio(counts["matched"], counts["output_facts"])
    return line


# Build both tables from per-patient rows: {row number: list of per-patient rows}.
def build_tables(row_data, age_sex_rows):
    buildup, by_group = [], []
    for number, rows in sorted(row_data.items()):
        totals = sum_counts(rows)
        for scope in score.SCOPES:
            buildup.append(make_line(
                {"row": number, "name": ROW_NAMES[number], "scope": scope, "patients": len(rows)},
                totals[scope]))
    for number in age_sex_rows:
        for age, sex in GROUPS:
            members = [r for r in row_data[number] if (r["age_band"], r["sex"]) == (age, sex)]
            totals = sum_counts(members)
            for scope in score.SCOPES:
                by_group.append(make_line(
                    {"row": number, "name": ROW_NAMES[number], "scope": scope,
                     "age_band": age, "sex": sex, "patients": len(members)},
                    totals[scope]))
    return buildup, by_group


BUILDUP_FIELDS = ["row", "name", "scope", "patients"] + TABLE_COUNTS + ["recall", "precision"]
BY_GROUP_FIELDS = ["row", "name", "scope", "age_band", "sex", "patients"] + TABLE_COUNTS + ["recall", "precision"]


# Messages about things that should be the same for every row (the answer keys do not change).
def sanity_messages(row_data):
    messages = []
    for scope in score.SCOPES:
        keys = {number: sum_counts(rows)[scope]["key_facts"] for number, rows in row_data.items()}
        if len(set(keys.values())) == 1:
            messages.append(f"ok: key facts ({scope}) are {next(iter(keys.values()))} in every row")
        else:
            messages.append(f"PROBLEM: key facts ({scope}) differ between rows: {keys}")
    return messages


# Write the two CSV files. Stops before writing anything shaped like a patient ID.
def write_tables(out_dir, buildup, by_group):
    out_dir = Path(out_dir)
    texts = {}
    for name, fields, lines in (("buildup_table.csv", BUILDUP_FIELDS, buildup),
                                ("by_age_sex.csv", BY_GROUP_FIELDS, by_group)):
        buffer = StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(lines)
        if ID_SHAPE.search(buffer.getvalue()):
            raise TableError(f"{name} would contain something shaped like a patient ID; not written")
        texts[name] = buffer.getvalue()
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in texts.items():
        with open(out_dir / name, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)


# Put a table on the screen, one block per scope.
def format_table(buildup):
    head = (f"{'row':>3}{'key':>6}{'match':>6}{'missed':>7}{'false':>6}{'wrongst':>8}"
            f"{'dupl':>5}{'dose ok':>8}{'dose bad':>9}{'conflicts':>11}{'recall':>8}{'prec':>7}")
    out = []
    for scope in score.SCOPES:
        title = "ALL FACTS" if scope == "all" else "CRITICAL FACTS (allergies and current medicines)"
        out += ["", title, head]
        for line in (l for l in buildup if l["scope"] == scope):
            conflicts = f"{line['conflict_shown']}/{line['conflict_facts']}"
            out.append(f"{line['row']:>3}{line['key_facts']:>6}{line['matched']:>6}"
                       f"{line['missed']:>7}{line['false_alarms']:>6}{line['wrong_status']:>8}"
                       f"{line['duplicates']:>5}{line['dose_correct']:>8}{line['dose_wrong']:>9}"
                       f"{conflicts:>11}{line['recall']:>8}{line['precision']:>7}")
    # The row names go in a legend, so the table stays narrow.
    out += ["", "Rows:"]
    out += [f"  {line['row']}: {line['name']}" for line in buildup if line["scope"] == "all"]
    return "\n".join(out)


# Run everything: read, check, add up, write. Returns what the screen needs.
def run(scores_root, out_dir, rows=None, age_sex_rows=(1, 7), expected_ids=None):
    rows = list(rows or ROW_NAMES)
    row_data = {}
    for number in rows:
        data = read_row(scores_root, number)
        check_row(data, number, expected_ids)
        row_data[number] = data
    buildup, by_group = build_tables(row_data, [n for n in age_sex_rows if n in row_data])
    write_tables(out_dir, buildup, by_group)
    return {"buildup": buildup, "by_group": by_group, "sanity": sanity_messages(row_data),
            "combination_keys_with_dose": sum(sum_counts(d)["all"]["combination_keys_with_dose"]
                                              for d in row_data.values())}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Held-out build-up table (T37). See the top of this file.")
    parser.add_argument("--scores-root", type=Path, default=SCORES_ROOT)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--age-sex-rows", type=int, nargs="+", default=[1, 7],
                        help="rows to break down by age and sex (default 1 and 7)")
    args = parser.parse_args(argv)
    try:
        result = run(args.scores_root, args.out_dir, age_sex_rows=args.age_sex_rows,
                     expected_ids=heldout_guard.heldout_ids())
    except TableError as error:
        raise SystemExit(f"stopped: {error}")
    print(format_table(result["buildup"]))
    print()
    for message in result["sanity"]:
        print(message)
    print(f"combination keys with a dose (warned by score.py, not scored): {result['combination_keys_with_dose']}")
    print(f"Wrote {args.out_dir / 'buildup_table.csv'} and {args.out_dir / 'by_age_sex.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
