"""Score the single-note public sets (T43, T40).

Usage (from the repo root, with the project venv):
    .venv/bin/python pipeline/eval/score_single_notes.py --set mtsamples
    .venv/bin/python pipeline/eval/score_single_notes.py --set traps

Every number comes from score.py: this script only prepares the two sides and then calls
score.score_patient and adds the counts up with score._sum_counts and score._ratio, exactly as
score.py does. Matching is not copied or changed here. It reads files and makes no model calls.
Only the IDs of the chosen set are accepted (D201-D212 for mtsamples, D101-D140 for traps);
anything else, held-out and reserve IDs included, is refused before any file is opened.

--set mtsamples (T43): the 12 MTSamples notes D201-D212. Files go to outputs/results/t43_mtsamples/.
- Type filter: only facts of type allergy or medicine, on BOTH sides (answer key and tool).
- Zone rule, tool side only. The answer keys were labelled inside the zone (the sections of a
  note the labellers read: pipeline/data/mtsamples/zones/<Mxxx>_zone.txt), so a tool fact from
  outside the zone could never match and would only add false alarms. A tool fact is kept only
  if its quote is inside the zone text, after all whitespace in both is collapsed to single
  spaces (so a quote that spreads over a line break still counts). A tool fact with no quote
  is kept, so it can only count against the tool. The number of facts the rule removes is printed.
- Files: per_patient.csv, summary.csv, failures.csv, and miss_causes.csv: one row per missed key
  fact with a cause: "wrong status", "found, no standard name" or "check by hand".

--set traps (T40): the 40 trap notes D101-D140, 20 pairs of a trap note and its twin
(pipeline/data/traps/trap_notes_pairs.csv). Files go to outputs/results/t40_traps/.
- Every note carries the same background line (atorvastatin, a medicine). Both sides are split
  into "background" (a medicine named atorvastatin) and "tested" (everything else), and each part
  is scored separately with score.score_patient. No zone rule and no type filter: all fact types count.
- A note is "right" when its tested part has 0 missed and 0 false alarms.
- Files: summary.csv (tested and background, all and critical), per_note.csv, pairs.csv
  (a pair is right-or-wrong for the trap note and for its twin), failures.csv.
- For the pair whose dose changed (pair 9) the script also prints a note on the tool's dose,
  history and dose_changed flag against the key. score.py does not score flags, so this is a
  note, not a count.
"""

import argparse
import csv
import re
import sys
from pathlib import Path

import score

# The two fact types the MTSamples scoring looks at.
KEEP_TYPES = ("allergy", "medicine")

DATA = score.DATA
RESULTS = score.REPO / "outputs" / "results"

# One entry per set.
SETS = {
    "mtsamples": {
        "ids": [f"D{n}" for n in range(201, 213)],
        "compiled_dir": score.REPO / "outputs" / "compiled" / "20261115-v2-mtsamples-sonnet-5-5",
        "keys_dir": DATA / "demo",
        "id_map": DATA / "mtsamples" / "id_map.csv",
        "zones_dir": DATA / "mtsamples" / "zones",
        "out_dir": RESULTS / "t43_mtsamples",
    },
    "traps": {
        "ids": [f"D{n}" for n in range(101, 141)],
        "compiled_dir": score.REPO / "outputs" / "compiled" / "20261115-v2-traps-sonnet-5-5",
        "keys_dir": DATA / "demo",
        "pairs": DATA / "traps" / "trap_notes_pairs.csv",
        "out_dir": RESULTS / "t40_traps",
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

# --- Traps: the background line, the two parts and the pairs file --------------------------

BACKGROUND_NAME = "atorvastatin"
PARTS = ("tested", "background")
# The counts shown per part in per_note.csv (all facts; the critical split is in summary.csv).
NOTE_FIELDS = ["key_facts", "output_facts", "matched", "missed", "false_alarms", "wrong_status",
               "duplicates", "dose_correct", "dose_wrong", "dose_not_applicable"]
PER_NOTE_FIELDS = (["patient_id", "pair", "role", "tested_right"]
                   + [f"{part}_{field}" for part in PARTS for field in NOTE_FIELDS])
PAIR_FIELDS = ["pair", "trap_id", "twin_id", "trap_role", "twin_role", "what_is_tested", "twin_tests",
               "trap_right", "twin_right"]
TRAP_FAILURE_FIELDS = FAILURE_FIELDS + ["part", "what_is_tested"]
SUMMARY_FIELDS = ["part", "scope", "patients"] + score.COUNT_FIELDS + ["recall", "precision"]
PARTNER_RE = re.compile(r"Pair: (D\d{3})")
# The pair whose dose changed: a note, not a count (score.py does not score flags).
DOSE_CHANGE_PAIR = 9


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


# --- Traps helpers ------------------------------------------------------------------------

def is_background(fact):
    """The background line: a medicine whose standard name is atorvastatin."""
    return fact["type"] == "medicine" and (fact.get("name") or "").strip().lower() == BACKGROUND_NAME


def split_note(compiled, key):
    """Split one note into its two parts, on both sides. Returns {"tested": (compiled, key),
    "background": (compiled, key)}. The tested part is every fact that is not the background line.
    The inputs are not changed."""
    parts = {}
    for part in PARTS:
        want_background = part == "background"
        tool = [f for f in compiled["facts"] if is_background(f) == want_background]
        keys = [f for f in key["facts"] if is_background(f) == want_background]
        parts[part] = ({**compiled, "facts": tool}, {**key, "facts": keys})
    return parts


def note_is_right(tested_result):
    """A note is right when its tested part has 0 missed and 0 false alarms."""
    counts = tested_result["counts"]["all"]
    return counts["missed"] == 0 and counts["false_alarms"] == 0


def load_pairs(path):
    """Read trap_notes_pairs.csv. Returns (notes, pairs).

    notes: {ID: row of the file}. pairs: a list, one per pair, in file order, each with the pair
    number (1, 2, ...), the trap note and the twin note. The partner of a note is named in its
    what_is_tested text ("Pair: D121"). The trap side is the row whose role starts with "trap"
    (trap or trap-control); the twin side starts with "twin". Checked so a typo cannot pair the wrong notes.
    """
    with open(path, encoding="utf-8", newline="") as handle:
        notes = {row["ID"]: row for row in csv.DictReader(handle)}
    pairs = []
    for note_id, row in notes.items():
        if not row["trap_or_twin"].startswith("trap"):
            continue
        match = PARTNER_RE.search(row["what_is_tested"])
        partner = notes.get(match.group(1)) if match else None
        if partner is None or not partner["trap_or_twin"].startswith("twin"):
            raise ValueError(f"{note_id}: its partner is missing or is not a twin note")
        back = PARTNER_RE.search(partner["what_is_tested"])
        if not back or back.group(1) != note_id:
            raise ValueError(f"{note_id} and {partner['ID']} do not name each other as partners")
        pairs.append({"pair": len(pairs) + 1, "trap": row, "twin": partner})
    paired = {p["trap"]["ID"] for p in pairs} | {p["twin"]["ID"] for p in pairs}
    if paired != set(notes):
        raise ValueError("some notes in the pairs file are not in a pair")
    return notes, pairs


def _fact_text(fact):
    """One fact in a few words, for printing: type name status."""
    return f"{fact['type']} {fact.get('name')} {fact['status']}"


def dose_change_note(key, compiled):
    """Plain lines comparing the tool's dose, history and dose_changed flag with the key, for each
    non-background medicine in the note. A note, not a count: score.py does not score flags."""
    lines = []
    for key_fact in key["facts"]:
        if key_fact["type"] != "medicine" or is_background(key_fact):
            continue
        tool_fact = next((f for f in compiled["facts"]
                          if f["type"] == "medicine" and f.get("name") == key_fact.get("name")), None)

        def history(fact):
            return [f"{h.get('dose')} {h.get('status')}" for h in fact["history"]]

        if tool_fact is None:
            lines.append(f"{key['patient_id']} {key_fact.get('name')}: the tool has no fact with this name")
            continue
        same_dose = score.dose_correct(key_fact, tool_fact)
        lines.append(
            f"{key['patient_id']} {key_fact.get('name')}: "
            f"key dose {key_fact.get('dose')}, history {history(key_fact)}, "
            f"dose_changed {'yes' if 'dose_changed' in key_fact['flags'] else 'no'}; "
            f"tool dose {tool_fact.get('dose')}, history {history(tool_fact)}, "
            f"dose_changed {'yes' if 'dose_changed' in tool_fact['flags'] else 'no'}; "
            f"dose matches the key: {'yes' if same_dose else 'no' if same_dose is False else 'not applicable'}")
    return lines


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


def _summary_rows(results, patient_count):
    """Totals from the counts, then recall and precision from the totals, as score.py does.
    Returns one row per scope."""
    totals = score._sum_counts(results)
    rows = []
    for scope in score.SCOPES:
        counts = totals[scope]
        rows.append({
            "scope": scope,
            "patients": patient_count,
            **counts,
            "recall": score._ratio(counts["matched"], counts["key_facts"]),
            "precision": score._ratio(counts["matched"], counts["output_facts"]),
        })
    return rows


def _count_row(pid, result):
    """One row of per_patient.csv for one note (age band and sex are blank for demo notes)."""
    row = {"patient_id": pid, "age_band": "", "sex": ""}
    for scope in score.SCOPES:
        for field in score.COUNT_FIELDS:
            row[f"{field}_{scope}"] = result["counts"][scope][field]
    return row


def _print_warnings(result):
    """Print score.py's warnings (they name only the patient and fact) to stderr."""
    for warning in result["warnings"]:
        print(warning["message"], file=sys.stderr)


# --- Running a set ------------------------------------------------------------------------

def run_mtsamples(config, patient_ids, out_dir):
    """Score the MTSamples notes and write the four CSV files."""
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
        _print_warnings(result)
        rows.append(_count_row(pid, result))
        failure_rows.extend(result["problems"])
        miss_rows.extend(miss_causes(key, compiled, result))

    summary_rows = _summary_rows(results, len(patient_ids))
    out_dir.mkdir(parents=True, exist_ok=True)
    score._write_csv(out_dir / "per_patient.csv", score._per_patient_fields(), rows)
    score._write_csv(out_dir / "summary.csv",
                     ["scope", "patients"] + score.COUNT_FIELDS + ["recall", "precision"], summary_rows)
    score._write_csv(out_dir / "failures.csv", FAILURE_FIELDS, failure_rows)
    score._write_csv(out_dir / "miss_causes.csv", MISS_FIELDS, miss_rows)

    print(f"Scored {len(patient_ids)} note(s) of set mtsamples: {', '.join(patient_ids)}")
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


def run_traps(config, patient_ids, out_dir):
    """Score the trap notes, each split into a tested part and a background part, and write the four CSV files."""
    notes, pairs = load_pairs(config["pairs"])
    role_of = {}
    pair_of = {}
    for pair in pairs:
        for side in ("trap", "twin"):
            role_of[pair[side]["ID"]] = pair[side]["trap_or_twin"]
            pair_of[pair[side]["ID"]] = pair["pair"]

    results = {part: [] for part in PARTS}
    per_note, failure_rows = [], []
    right = {}
    records = {}
    for pid in patient_ids:
        compiled = score.load_json(config["compiled_dir"] / f"{pid}.json")
        key = score.load_json(score._find_key(config["keys_dir"], pid))
        _unique_fact_ids(compiled, "tool record")
        _unique_fact_ids(key, "answer key")
        records[pid] = (compiled, key)

        parts = split_note(compiled, key)
        row = {"patient_id": pid, "pair": pair_of[pid], "role": role_of[pid]}
        for part in PARTS:
            part_compiled, part_key = parts[part]
            # The scoring itself is score.py's, unchanged.
            result = score.score_patient(part_compiled, part_key)
            results[part].append(result)
            _print_warnings(result)
            for field in NOTE_FIELDS:
                row[f"{part}_{field}"] = result["counts"]["all"][field]
            for problem in result["problems"]:
                failure_rows.append({**problem, "part": part, "what_is_tested": notes[pid]["what_is_tested"]})
            if part == "tested":
                right[pid] = note_is_right(result)
        row["tested_right"] = right[pid]
        per_note.append(row)

    pair_rows = []
    for pair in pairs:
        trap_id, twin_id = pair["trap"]["ID"], pair["twin"]["ID"]
        if trap_id not in right or twin_id not in right:
            continue  # a subset run: only pairs with both notes scored
        pair_rows.append({
            "pair": pair["pair"], "trap_id": trap_id, "twin_id": twin_id,
            "trap_role": pair["trap"]["trap_or_twin"], "twin_role": pair["twin"]["trap_or_twin"],
            "what_is_tested": pair["trap"]["what_is_tested"], "twin_tests": pair["twin"]["what_is_tested"],
            "trap_right": right[trap_id], "twin_right": right[twin_id],
        })

    summary_rows = []
    for part in PARTS:
        for row in _summary_rows(results[part], len(patient_ids)):
            summary_rows.append({"part": part, **row})

    out_dir.mkdir(parents=True, exist_ok=True)
    score._write_csv(out_dir / "summary.csv", SUMMARY_FIELDS, summary_rows)
    score._write_csv(out_dir / "per_note.csv", PER_NOTE_FIELDS, per_note)
    score._write_csv(out_dir / "pairs.csv", PAIR_FIELDS, pair_rows)
    score._write_csv(out_dir / "failures.csv", TRAP_FAILURE_FIELDS, failure_rows)

    print(f"Scored {len(patient_ids)} note(s) of set traps")
    for row in summary_rows:
        print(f"{row['part']:>10} {row['scope']:>8}: key {row['key_facts']}, tool {row['output_facts']}, "
              f"matched {row['matched']}, missed {row['missed']}, false alarms {row['false_alarms']}, "
              f"wrong status {row['wrong_status']}, duplicates {row['duplicates']}, "
              f"dose correct {row['dose_correct']}, dose wrong {row['dose_wrong']}, "
              f"dose n/a {row['dose_not_applicable']}, recall {row['recall']}, precision {row['precision']}")
    print(f"Trap notes right: {sum(r['trap_right'] for r in pair_rows)} of {len(pair_rows)} "
          f"(roles: {sum(1 for r in pair_rows if r['trap_role'] == 'trap-control')} trap-control)")
    print(f"Twin notes right: {sum(r['twin_right'] for r in pair_rows)} of {len(pair_rows)} "
          f"(roles: {sum(1 for r in pair_rows if r['twin_role'] == 'twin-control')} twin-control)")
    background = results["background"]
    totals = score._sum_counts(background)["all"]
    print(f"Background line: matched {totals['matched']} of {totals['key_facts']}; "
          f"dose correct {totals['dose_correct']}, dose wrong {totals['dose_wrong']}")
    tested_totals = score._sum_counts(results["tested"])["all"]
    print(f"Tested part: dose correct {tested_totals['dose_correct']}, dose wrong {tested_totals['dose_wrong']}")
    print(f"Failure rows: {len(failure_rows)}")
    for failure in failure_rows:
        tests = PARTNER_RE.sub("", notes[failure["patient_id"]]["what_is_tested"]).strip()
        key_side = (f"{failure['type']} {failure['name']} {failure['key_status']}"
                    if failure["key_fact_id"] else "-")
        tool_side = (f"{failure['type']} {failure['name']} {failure['output_status']}"
                     if failure["output_fact_id"] else "-")
        print(f"  {failure['patient_id']} [{failure['part']}] {failure['kind']} | tests: {tests} | "
              f"key: {key_side} | tool: {tool_side}")
    for pair in pairs:
        if pair["pair"] == DOSE_CHANGE_PAIR and pair["trap"]["ID"] in records and pair["twin"]["ID"] in records:
            print(f"Pair {DOSE_CHANGE_PAIR} dose-change note (flags are not scored):")
            for side in ("trap", "twin"):
                compiled, key = records[pair[side]["ID"]]
                for line in dose_change_note(key, compiled):
                    print(f"  {line}")
    print(f"Wrote summary.csv, per_note.csv, pairs.csv and failures.csv in {out_dir}")


RUNNERS = {"mtsamples": run_mtsamples, "traps": run_traps}


def main(argv=None):
    """Score the chosen single-note set and write its CSV files."""
    parser = argparse.ArgumentParser(description="Score single-note public sets (T43 MTSamples, T40 traps).")
    parser.add_argument("--set", dest="set_name", required=True, choices=sorted(SETS), help="which set to score")
    parser.add_argument("--patients", nargs="+", metavar="ID",
                        help="a subset of the set's IDs (default: all of them)")
    parser.add_argument("--out-dir", type=Path, help="folder for the CSV files (default: the set's results folder)")
    args = parser.parse_args(argv)

    config = SETS[args.set_name]
    patient_ids = list(dict.fromkeys(args.patients or config["ids"]))
    _check_ids(patient_ids, config["ids"])
    RUNNERS[args.set_name](config, patient_ids, args.out_dir or config["out_dir"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
