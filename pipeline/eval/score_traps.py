"""Trap breakdown (T37): how many planted trap cases each method got right.

Usage (from the repo root, with the project venv):
    .venv/bin/python pipeline/eval/score_traps.py

A trap is a planted case, listed in pipeline/data/traps/heldout_traps.csv and reserve_traps.csv.
For each trap this script looks up the matching fact in the patient's ANSWER KEY (same type and
generic name). Team decision Q08: traps are scored against the answer key, never against the
trap's right_answer text, and a trap label is never edited.

Then, for each method (default: row 1 keyword baseline and row 7 full tool), it asks: does that
method's record have a fact with the same type, name and status as the key fact?
    caught            yes
    not_caught        no
    label_overtaken   the trap label expects one status but the key says another (T33 found 3,
                      all stop_one_hospital). The label is out of date, so this is not scored as a
                      miss. It gets its own count.
    key_fact_not_found  the key has no fact with that type and name (reported, never guessed)
The label's expected status is read from its right_answer words ("stopped", or "current" /
"kept" for the others). It is only used to spot an overtaken label, never to score.

Two counts are kept for every trap type, so both are shown:
    caught_dose_not_checked   the method has a fact with the key's type, name and status
                              (the first rule, which ignores doses)
    caught                    the same, and for dose_change traps also the right dose. A
                              dose_change trap is caught only if (1) the matched fact has the
                              key's dose (score.py's own comparison, so 1 g = 1000 mg) and (2) no
                              other fact of the same type and name is also "current" with a
                              different dose. An output fact that itself matches another key fact
                              (score.py's one-to-one matching) is ignored for (2): that is a
                              second real entry in the key, not a stray extra. This refinement was
                              added after the first trap run, because the first version penalised
                              output that matched the key. If the key has no dose, or is a combination medicine
                              (never dose-scored, T12), the dose rule is not applicable and the
                              trap counts as caught on the first rule. For the other three trap
                              types caught equals caught_dose_not_checked.
not_caught is the scored traps that are not caught under the stricter rule.

Writes:
    outputs/results_heldout/traps/per_trap.csv   one line per trap, with patient IDs and names.
                                                 Git-ignored, never committed.
    outputs/results/heldout/traps_by_type.csv    counts per trap type and method. No IDs, no names.
The screen shows counts only. No model calls. Before any held-out file is opened, the script
checks the `freeze` tag exists and the detail folder is git-ignored (heldout_guard.py).
"""

import argparse
import csv
import json
import re
import sys
from io import StringIO
from pathlib import Path

import heldout_guard
import heldout_table
import score  # the same dose comparison as the scoring itself (1 g = 1000 mg)

REPO = Path(__file__).resolve().parents[2]
TRAPS_DIR = REPO / "pipeline" / "data" / "traps"
TRAP_FILES = ("heldout_traps.csv", "reserve_traps.csv")
DETAIL_DIR = REPO / "outputs" / "results_heldout" / "traps"
OUT_DIR = REPO / "outputs" / "results" / "heldout"

# The methods compared by default: row number -> folder of compiled-shape records.
DEFAULT_ROWS = {
    1: REPO / "outputs" / "results_heldout" / "baseline_keyword",
    7: REPO / "outputs" / "compiled" / "20261115-v2-heldout-sonnet-5-5",
}
TRAP_TYPES = ("silent_medicine", "dose_change", "stop_one_hospital", "allergy_missed")
OUTCOMES = ("caught", "not_caught", "label_overtaken", "key_fact_not_found")
ID_SHAPE = re.compile(r"\b[PRD]\d{3}\b")

TYPE_FIELDS = ["trap_type", "row", "method", "traps", "caught", "caught_dose_not_checked",
               "not_caught", "label_overtaken", "key_fact_not_found", "caught_of_scored"]


class TrapError(Exception):
    """A check failed. The message gives counts only."""


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# The status a trap label expects, read from its right_answer words. None if it cannot be read.
def expected_status(right_answer):
    text = right_answer.lower()
    if re.search(r"\bstopped\b", text):
        return "stopped"
    if "current" in text or "kept" in text:
        return "current"
    return None


def _name(fact):
    name = fact.get("name")
    return name.strip().lower() if name else None


# Key facts with the trap's type and name. The one whose status matches the label comes first.
def key_matches(trap, key_facts):
    want = (trap["fact_type"], trap["fact_name"].strip().lower())
    found = [f for f in key_facts if (f["type"], _name(f)) == want]
    label = expected_status(trap["right_answer"])
    return sorted(found, key=lambda f: f["status"] != label)


# Statuses a method's record gives to the trap's type and name (for the detail file).
def statuses_in(record_facts, fact_type, name):
    return [f["status"] for f in record_facts if (f["type"], _name(f)) == (fact_type, name)]


# The dose rule for a dose_change trap. key is the trap's key fact, key_facts all the patient's key
# facts, facts the method's output facts. Output facts are paired with key facts one to one by
# score.py's own matching, so an output fact that matches another key fact is never counted as a stray.
#   not_applicable      the key has no dose, or is a combination medicine (never dose-scored)
#   no_own_match        every output fact with the key's status is already matched to another key fact
#   wrong_dose          the output fact matched to this key fact does not have the key's dose
#   other_current_dose  the matched fact has the key's dose, but another output fact of the same type
#                       and name, matched to no key fact, is also "current" with a different dose
#   ok                  the matched fact has the key's dose and no such other fact exists
def dose_check(key, key_facts, facts):
    if key.get("dose") is None or score.is_combination(key):
        return "not_applicable"
    ki = next(i for i, k in enumerate(key_facts) if k is key)
    pairs = score._match(key_facts, facts)[0]
    if ki not in pairs:
        return "no_own_match"
    if score.dose_correct(key, facts[pairs[ki]]) is not True:
        return "wrong_dose"
    wanted = score._dose_value(key["dose"])
    matched_to_a_key = set(pairs.values())
    for oi, f in enumerate(facts):
        if (oi not in matched_to_a_key and (f["type"], _name(f)) == (key["type"], _name(key))
                and f["status"] == "current" and score._dose_value(f.get("dose")) != wanted):
            return "other_current_dose"
    return "ok"


# Score one trap. records is {row number: list of that method's facts for this patient}.
# Returns the outcome for every row (under the stricter dose rule), plus the details for the
# detail file: detail["loose"][row] is the first rule (dose not checked), detail["dose_check"][row]
# the verdict of the dose rule (dose_change traps only).
def score_trap(trap, key_facts, records):
    matches = key_matches(trap, key_facts)
    label = expected_status(trap["right_answer"])
    detail = {"label_status": label, "key_status": None, "key_matches": len(matches),
              "loose": {row: False for row in records}, "dose_check": {row: "" for row in records}}
    if not matches:
        return {row: "key_fact_not_found" for row in records}, detail
    key = matches[0]
    detail["key_status"] = key["status"]
    if label is not None and key["status"] != label:
        return {row: "label_overtaken" for row in records}, detail
    outcomes = {}
    for row, facts in records.items():
        loose = any((f["type"], _name(f), f["status"]) == (key["type"], _name(key), key["status"]) for f in facts)
        detail["loose"][row] = loose
        caught = loose
        if loose and trap["trap"] == "dose_change":
            detail["dose_check"][row] = dose_check(key, key_facts, facts)
            caught = detail["dose_check"][row] in ("ok", "not_applicable")
        outcomes[row] = "caught" if caught else "not_caught"
    return outcomes, detail


# Add up outcomes per trap type and row. Adds a line "all" for the total of every type.
def count_by_type(scored, rows):
    lines = []
    for trap_type in list(TRAP_TYPES) + ["all"]:
        for row in rows:
            counts = dict.fromkeys(OUTCOMES, 0)
            traps = 0
            for item in scored:
                if trap_type == "all" or item["trap"] == trap_type:
                    traps += 1
                    counts[item["outcomes"][row]] += 1
            scored_n = counts["caught"] + counts["not_caught"]
            loose = sum(item["loose"][row] for item in scored if trap_type in ("all", item["trap"]))
            lines.append({
                "trap_type": trap_type, "row": row, "method": heldout_table.ROW_NAMES.get(row, ""),
                "traps": traps, **counts, "caught_dose_not_checked": loose,
                "caught_of_scored": round(counts["caught"] / scored_n, 3) if scored_n else "",
            })
    return lines


# Read the trap files and check they hold what they should. Counts only in messages.
def read_traps(traps_dir, expected_ids=None):
    traps = []
    for name in TRAP_FILES:
        with open(Path(traps_dir) / name, encoding="utf-8", newline="") as handle:
            traps.extend(csv.DictReader(handle))
    unknown = {t["trap"] for t in traps} - set(TRAP_TYPES)
    if unknown:
        raise TrapError(f"{len(unknown)} unknown trap types in the trap files")
    unreadable = sum(expected_status(t["right_answer"]) is None for t in traps)
    if unreadable:
        raise TrapError(f"{unreadable} trap labels have no readable expected status")
    if expected_ids is not None:
        outside = len({t["patient_id"] for t in traps} - set(expected_ids))
        if outside:
            raise TrapError(f"{outside} trap patients are not held-out patients")
    return traps


# Score every trap. key_for(pid) and record_for(row, pid) load the files, so tests can fake them.
def run(traps, rows, key_for, record_for):
    scored = []
    for trap in traps:
        pid = trap["patient_id"]
        key_facts = key_for(pid)["facts"]
        records = {row: record_for(row, pid)["facts"] for row in rows}
        outcomes, detail = score_trap(trap, key_facts, records)
        item = {"patient_id": pid, "trap": trap["trap"], "fact_type": trap["fact_type"],
                "fact_name": trap["fact_name"], "outcomes": outcomes, **detail}
        item["found"] = {row: statuses_in(records[row], trap["fact_type"], trap["fact_name"].strip().lower())
                         for row in rows}
        item["current_doses"] = {row: [str(f.get("dose")) for f in records[row]
                                       if (f["type"], _name(f)) == (trap["fact_type"], trap["fact_name"].strip().lower())
                                       and f["status"] == "current"] for row in rows}
        scored.append(item)
    return scored


def csv_text(fields, lines):
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(lines)
    return buffer.getvalue()


# Write the per-trap detail (git-ignored folder) and the per-type counts (committable, no IDs).
def write_outputs(scored, rows, detail_dir, out_dir):
    detail_fields = ["patient_id", "trap", "fact_type", "fact_name", "label_status", "key_status", "key_matches"]
    for row in rows:
        detail_fields += [f"row{row}_outcome", f"row{row}_caught_dose_not_checked", f"row{row}_dose_check",
                          f"row{row}_statuses_found", f"row{row}_current_doses"]
    detail_lines = []
    for item in scored:
        line = {k: item[k] for k in detail_fields[:7]}
        for row in rows:
            line[f"row{row}_outcome"] = item["outcomes"][row]
            line[f"row{row}_caught_dose_not_checked"] = item["loose"][row]
            line[f"row{row}_dose_check"] = item["dose_check"][row]
            line[f"row{row}_statuses_found"] = "|".join(item["found"][row])
            line[f"row{row}_current_doses"] = "|".join(item["current_doses"][row])
        detail_lines.append(line)
    by_type = count_by_type(scored, rows)
    type_text = csv_text(TYPE_FIELDS, by_type)
    if ID_SHAPE.search(type_text):
        raise TrapError("traps_by_type.csv would contain something shaped like a patient ID; not written")
    Path(detail_dir).mkdir(parents=True, exist_ok=True)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(detail_dir) / "per_trap.csv").write_text(csv_text(detail_fields, detail_lines), encoding="utf-8", newline="")
    (Path(out_dir) / "traps_by_type.csv").write_text(type_text, encoding="utf-8", newline="")
    return by_type


def format_counts(by_type, rows):
    head = (f"{'trap type':<20}{'row':>4}{'traps':>6}{'caught':>7}{'dose not':>9}{'not':>5}{'overtaken':>10}"
            f"{'no key':>7}{'caught/scored':>14}")
    sub = f"{'':<20}{'':>4}{'':>6}{'':>7}{'checked':>9}"
    out = [head, sub]
    for line in by_type:
        out.append(f"{line['trap_type']:<20}{line['row']:>4}{line['traps']:>6}{line['caught']:>7}"
                   f"{line['caught_dose_not_checked']:>9}{line['not_caught']:>5}{line['label_overtaken']:>10}"
                   f"{line['key_fact_not_found']:>7}{line['caught_of_scored']:>14}")
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Trap breakdown (T37). See the top of this file.")
    parser.add_argument("--traps-dir", type=Path, default=TRAPS_DIR)
    parser.add_argument("--detail-dir", type=Path, default=DETAIL_DIR)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)
    rows = list(DEFAULT_ROWS)

    # Held-out guard first: the freeze tag must exist and the detail folder must be git-ignored.
    heldout_guard.require_heldout_ok([args.detail_dir / "per_trap.csv"])
    try:
        traps = read_traps(args.traps_dir, heldout_guard.heldout_ids())
        scored = run(
            traps, rows,
            key_for=lambda pid: load_json(heldout_guard.patient_folder(pid) / f"{pid}_key.json"),
            record_for=lambda row, pid: load_json(DEFAULT_ROWS[row] / f"{pid}.json"),
        )
        by_type = write_outputs(scored, rows, args.detail_dir, args.out_dir)
    except (TrapError, FileNotFoundError) as error:
        raise SystemExit(f"stopped: {error}")
    print(f"{len(scored)} traps in {len({s['patient_id'] for s in scored})} patients")
    print(format_counts(by_type, rows))
    print("Rows: " + "; ".join(f"{r} = {heldout_table.ROW_NAMES[r]}" for r in rows))
    print(f"Wrote {args.out_dir / 'traps_by_type.csv'} (no IDs) and {args.detail_dir / 'per_trap.csv'} (git-ignored)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
