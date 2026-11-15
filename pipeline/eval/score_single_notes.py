"""Score the single-note public sets (T43): allergies and medicines only.

Usage (from the repo root, with the project venv):
    .venv/bin/python pipeline/eval/score_single_notes.py --set mtsamples

--set mtsamples scores the 12 MTSamples notes D201-D212. Every number comes from score.py:
this script only prepares the two sides and then calls score.score_patient and adds the counts
up with score._sum_counts and score._ratio, exactly as score.py does. Matching is not copied or
changed here. It reads files and makes no model calls. Only the IDs of the chosen set are
accepted (D201-D212 for mtsamples); anything else, held-out and reserve IDs included, is
refused before any file is opened.

What is kept (the same two rules on every note):
- Type filter: only facts of type allergy or medicine, on BOTH sides (answer key and tool).
- Zone rule, tool side only. The answer keys were labelled inside the zone (the sections of a
  note the labellers read: pipeline/data/mtsamples/zones/<Mxxx>_zone.txt), so a tool fact from
  outside the zone could never match and would only add false alarms. A tool fact is kept only
  if its quote is inside the zone text, after all whitespace in both is collapsed to single
  spaces (so a quote that spreads over a line break still counts). A tool fact with no quote
  is kept, so it can only count against the tool. The number of facts the rule removes is printed.

Files written to outputs/results/t43_mtsamples/ (same columns as score.py where score.py has them):
per_patient.csv, summary.csv, failures.csv, and miss_causes.csv: one row per missed key fact
with a cause: "wrong status", "found, no standard name" or "check by hand".

A later --set traps (T40 trap notes D101-D140) is meant to be added to SETS below; it is not built yet.
"""

import argparse
import csv
import sys
from pathlib import Path

import score

# The two fact types this scoring looks at.
KEEP_TYPES = ("allergy", "medicine")

DATA = score.DATA
RESULTS = score.REPO / "outputs" / "results"

# One entry per set. Add the traps set here later (Prompt 5).
SETS = {
    "mtsamples": {
        "ids": [f"D{n}" for n in range(201, 213)],
        "compiled_dir": score.REPO / "outputs" / "compiled" / "20261115-v2-mtsamples-sonnet-5-5",
        "keys_dir": DATA / "demo",
        "id_map": DATA / "mtsamples" / "id_map.csv",
        "zones_dir": DATA / "mtsamples" / "zones",
        "out_dir": RESULTS / "t43_mtsamples",
    },
}

# failures.csv has the same columns as score.py's (score.py writes them inline, so they are
# repeated here; a test checks that the two headers stay the same).
FAILURE_FIELDS = [
    "patient_id", "kind", "key_fact_id", "output_fact_id", "type", "name", "key_status", "output_status",
    "key_critical", "output_critical", "duplicate", "key_quote", "output_quote",
]
MISS_FIELDS = ["patient_id", "key_fact_id", "name", "name_as_written", "key_status", "cause"]

CAUSE_WRONG_STATUS = "wrong status"
CAUSE_NO_STANDARD_NAME = "found, no standard name"
CAUSE_BY_HAND = "check by hand"


def collapse_whitespace(text):
    """Turn every run of spaces, tabs and line breaks into one space, and trim the ends."""
    return " ".join(text.split())


def load_id_map(path):
    """Read id_map.csv into {demo ID: MTSamples ID}, for example {"D201": "M001"}."""
    with open(path, encoding="utf-8", newline="") as handle:
        return {row["demo_id"]: row["mtsamples_id"] for row in csv.DictReader(handle)}


def keep_allergies_and_medicines(facts):
    """The type filter: keep only allergy and medicine facts."""
    return [fact for fact in facts if fact["type"] in KEEP_TYPES]


def apply_zone_rule(tool_facts, zone_text):
    """Keep a tool fact only if its quote is inside the zone text (whitespace collapsed on both
    sides). A fact with no quote is kept. Returns (kept facts, number removed)."""
    zone = collapse_whitespace(zone_text)
    kept = []
    for fact in tool_facts:
        quote = fact.get("quote")
        if not quote or not quote.strip() or collapse_whitespace(quote) in zone:
            kept.append(fact)
    return kept, len(tool_facts) - len(kept)


def filter_note(compiled, key, zone_text):
    """Prepare one note: type filter on both sides, then the zone rule on the tool side.
    Returns (filtered compiled record, filtered key, number of tool facts the zone rule removed).
    The inputs are not changed."""
    tool_facts, removed = apply_zone_rule(keep_allergies_and_medicines(compiled["facts"]), zone_text)
    key_facts = keep_allergies_and_medicines(key["facts"])
    return {**compiled, "facts": tool_facts}, {**key, "facts": key_facts}, removed


def count_unnamed(tool_facts):
    """Returns (facts with an empty standard name, facts carrying the unknown_name flag)."""
    empty_name = sum(1 for fact in tool_facts if not fact.get("name"))
    unknown = sum(1 for fact in tool_facts if "unknown_name" in fact.get("flags", []))
    return empty_name, unknown


def _written(fact):
    """The name as the source wrote it, trimmed and lowercase, or None."""
    value = fact.get("name_as_written")
    return value.strip().lower() if value and value.strip() else None


def miss_causes(key, compiled, result):
    """One row per missed key fact, with a cause, using the result score.score_patient gave.

    "wrong status": score_patient reported it as a wrong-status pair.
    "found, no standard name": a tool fact in the same note that no key fact matched, with the
        same type and status, an empty standard name, and the same name as written.
    "check by hand": anything else.
    """
    patient_id = key["patient_id"]
    key_by_id = {fact["fact_id"]: fact for fact in key["facts"]}
    tool_by_id = {fact["fact_id"]: fact for fact in compiled["facts"]}
    wrong_ids = {p["key_fact_id"] for p in result["problems"] if p["kind"] == "wrong_status"}
    missed_ids = [p["key_fact_id"] for p in result["problems"] if p["kind"] in ("missed", "wrong_status")]
    # Tool facts no key fact matched exactly: the false alarms, and the tool side of wrong-status pairs.
    unmatched = [tool_by_id[p["output_fact_id"]] for p in result["problems"]
                 if p["output_fact_id"] is not None and p["kind"] in ("false_alarm", "wrong_status")]

    rows = []
    for fact_id in missed_ids:
        fact = key_by_id[fact_id]
        if fact_id in wrong_ids:
            cause = CAUSE_WRONG_STATUS
        elif any(not out.get("name") and out["type"] == fact["type"] and out["status"] == fact["status"]
                 and _written(out) is not None and _written(out) == _written(fact)
                 for out in unmatched):
            cause = CAUSE_NO_STANDARD_NAME
        else:
            cause = CAUSE_BY_HAND
        rows.append({
            "patient_id": patient_id,
            "key_fact_id": fact_id,
            "name": fact.get("name"),
            "name_as_written": fact.get("name_as_written"),
            "key_status": fact["status"],
            "cause": cause,
        })
    return rows


def _check_ids(patient_ids, allowed_ids):
    """Refuse any ID outside the chosen set. Runs before any file is opened."""
    for pid in patient_ids:
        if pid not in allowed_ids:
            raise SystemExit(f"{pid} is not in this set. Allowed IDs: {allowed_ids[0]} to {allowed_ids[-1]}.")


def _unique_fact_ids(record, what):
    """Fact IDs must be unique inside one record (record_format.md); miss_causes relies on it."""
    ids = [fact["fact_id"] for fact in record["facts"]]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{record['patient_id']}: duplicate fact_id in the {what}")


def main(argv=None):
    """Score the chosen single-note set and write the four CSV files."""
    parser = argparse.ArgumentParser(description="Score single-note public sets (T43), allergies and medicines only.")
    parser.add_argument("--set", dest="set_name", required=True, choices=sorted(SETS), help="which set to score")
    parser.add_argument("--patients", nargs="+", metavar="ID",
                        help="a subset of the set's IDs (default: all of them)")
    parser.add_argument("--out-dir", type=Path, help="folder for the CSV files (default: outputs/results/t43_<set>)")
    args = parser.parse_args(argv)

    config = SETS[args.set_name]
    patient_ids = list(dict.fromkeys(args.patients or config["ids"]))
    _check_ids(patient_ids, config["ids"])
    out_dir = args.out_dir or config["out_dir"]

    id_map = load_id_map(config["id_map"])
    results, rows, failure_rows, miss_rows = [], [], [], []
    removed_by_note = {}
    tool_facts_scored = []
    for pid in patient_ids:
        if pid not in id_map:
            raise SystemExit(f"{pid} has no row in {config['id_map'].name}")
        zone_path = config["zones_dir"] / f"{id_map[pid]}_zone.txt"
        with open(zone_path, encoding="utf-8") as handle:
            zone_text = handle.read()
        compiled = score.load_json(config["compiled_dir"] / f"{pid}.json")
        key = score.load_json(score._find_key(config["keys_dir"], pid))
        _unique_fact_ids(compiled, "tool record")
        _unique_fact_ids(key, "answer key")

        compiled, key, removed = filter_note(compiled, key, zone_text)
        removed_by_note[pid] = removed
        tool_facts_scored.extend(compiled["facts"])

        # The scoring itself is score.py's, unchanged.
        result = score.score_patient(compiled, key)
        results.append(result)
        for warning in result["warnings"]:
            print(warning["message"], file=sys.stderr)
        row = {"patient_id": pid, "age_band": "", "sex": ""}
        for scope in score.SCOPES:
            for field in score.COUNT_FIELDS:
                row[f"{field}_{scope}"] = result["counts"][scope][field]
        rows.append(row)
        failure_rows.extend(result["problems"])
        miss_rows.extend(miss_causes(key, compiled, result))

    # Totals are summed from the counts, then recall and precision are worked out from the totals.
    totals = score._sum_counts(results)
    summary_rows = []
    for scope in score.SCOPES:
        counts = totals[scope]
        summary_rows.append({
            "scope": scope,
            "patients": len(patient_ids),
            **counts,
            "recall": score._ratio(counts["matched"], counts["key_facts"]),
            "precision": score._ratio(counts["matched"], counts["output_facts"]),
        })

    out_dir.mkdir(parents=True, exist_ok=True)
    score._write_csv(out_dir / "per_patient.csv", score._per_patient_fields(), rows)
    score._write_csv(out_dir / "summary.csv",
                     ["scope", "patients"] + score.COUNT_FIELDS + ["recall", "precision"], summary_rows)
    score._write_csv(out_dir / "failures.csv", FAILURE_FIELDS, failure_rows)
    score._write_csv(out_dir / "miss_causes.csv", MISS_FIELDS, miss_rows)

    print(f"Scored {len(patient_ids)} note(s) of set {args.set_name}: {', '.join(patient_ids)}")
    for summary in summary_rows:
        print(f"{summary['scope']:>8}: key {summary['key_facts']}, tool {summary['output_facts']}, "
              f"matched {summary['matched']}, missed {summary['missed']}, "
              f"false alarms {summary['false_alarms']}, wrong status {summary['wrong_status']}, "
              f"duplicates {summary['duplicates']}, dose correct {summary['dose_correct']}, "
              f"dose wrong {summary['dose_wrong']}, dose n/a {summary['dose_not_applicable']}, "
              f"recall {summary['recall']}, precision {summary['precision']}")
    print(f"Zone rule removed {sum(removed_by_note.values())} allergy/medicine tool fact(s): "
          + ", ".join(f"{pid} {n}" for pid, n in removed_by_note.items()))
    causes = {}
    for miss in miss_rows:
        causes[miss["cause"]] = causes.get(miss["cause"], 0) + 1
    print("Miss causes: " + (", ".join(f"{cause} {n}" for cause, n in sorted(causes.items())) or "none"))
    empty_name, unknown = count_unnamed(tool_facts_scored)
    print(f"Tool allergy/medicine facts scored: {len(tool_facts_scored)}; with an empty standard name: "
          f"{empty_name}; carrying the unknown_name flag: {unknown}")
    print(f"Wrote per_patient.csv, summary.csv, failures.csv and miss_causes.csv in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
