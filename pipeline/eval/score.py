"""Scoring (T18): compare one patient's compiled record with their answer key.

Usage (from the repo root, with the project venv):
    .venv/bin/python pipeline/eval/score.py --compiled-dir DIR --keys-dir DIR \
        --patients P001 P002 --out-dir DIR

--compiled-dir holds <ID>.json (compiled shape). --keys-dir holds <ID>_key.json, either
directly inside it or inside an <ID>/ folder (the layout of pipeline/data/working and
pipeline/data/demo). The script writes per_patient.csv, summary.csv and failures.csv into
--out-dir. It only reads files and makes no model calls.

Only D001 and P001 to P020 are accepted unless --include-heldout is given. The check runs
before any file is opened, so a held-out or reserve record cannot be read by accident.

Methodology (set by the team; do not change it here):
- A key fact and an output fact match only if type, generic name (case-insensitive) and
  status all match. Each key fact matches at most one output fact.
- Missed case = key fact with no match. False alarm = output fact with no match.
- Wrong status = an unmatched key fact and an unmatched output fact with the same type and
  name but a different status. It counts as 1 missed and 1 false alarm, and also in the
  wrong_status column.
- Duplicate = unmatched output fact with the same type, name and status as a matched fact.
  It counts as a false alarm, and also in the duplicates column.
- For matched medicines, dose_correct is true, false or not applicable (the key has no dose).
- conflict_shown: a key fact with the conflict flag counts only if its output side and every
  other fact in its conflict group are matched to output facts that also carry the conflict flag.
- Critical facts = allergies and current medicines. Every count is given for all facts and
  for critical facts only.

Choices the methodology left open (also recorded in docs/decisions.md):
- When more than one output fact could match a key fact, the one with the correct dose is
  taken first; otherwise the first in file order.
- Doses are compared after converting grams to milligrams, so "1 g" equals "1000 mg".
  record_format.md treats these as the same dose.
- Matching uses all facts. The critical slice then uses each fact's own criticality: a missed
  case by its key fact, a false alarm by its output fact. A wrong-status pair counts as
  missed by its key fact and as wrong_status and false alarm by its output fact.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

# Repo root is two folders up from this file (pipeline/eval/score.py).
REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "pipeline" / "data"
PATIENTS_CSV = DATA / "patients.csv"

# A dose written as "<number> <unit>", for example "1000 mg" or "1 g".
DOSE_RE = re.compile(r"^(\d+(?:\.\d+)?) (mg|mcg|g|mL|units|puffs|drops)$")

# Every count, in the order the CSV files list them.
COUNT_FIELDS = [
    "key_facts", "output_facts", "matched", "missed", "false_alarms",
    "wrong_status", "duplicates", "dose_correct", "dose_wrong",
    "dose_not_applicable", "conflict_facts", "conflict_shown",
]
SCOPES = ("all", "critical")

# Patients scored without --include-heldout: the 20 working patients and the demo patient.
WORKING_RE = re.compile(r"^P0(?:0[1-9]|1[0-9]|20)$")
DEMO_ID = "D001"
ANY_SPLIT_ID_RE = re.compile(r"^[PR]\d{3}$")


def load_json(path):
    """Read one JSON file as UTF-8."""
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def is_critical(fact):
    """Critical facts are allergies and current medicines."""
    return fact["type"] == "allergy" or (fact["type"] == "medicine" and fact["status"] == "current")


def _name(fact):
    """Generic name used for matching: lowercase, or None when the record has no name."""
    name = fact.get("name")
    return name.strip().lower() if name else None


def _dose_value(dose):
    """Turn a dose into a comparable value. Grams become milligrams, so "1 g" equals "1000 mg"."""
    if dose is None:
        return None
    text = dose.strip()
    match = DOSE_RE.match(text)
    if not match:
        return text
    value, unit = float(match.group(1)), match.group(2)
    if unit == "g":
        return (value * 1000, "mg")
    return (value, unit)


def dose_correct(key_fact, out_fact):
    """True or False for a matched medicine. None (not applicable) when the key gives no dose."""
    if key_fact.get("dose") is None:
        return None
    return _dose_value(key_fact["dose"]) == _dose_value(out_fact.get("dose"))


def _match(key_facts, out_facts):
    """Pair key facts with output facts.

    Returns (pairs, wrong, duplicates, false_alarms):
      pairs: {key index: output index} for exact matches (type, name and status all equal).
      wrong: {key index: output index} for wrong-status pairs (same type and name, other status).
      duplicates: output indexes left over that repeat a matched fact's type, name and status.
      false_alarms: the other output indexes left over.
    """
    # Step 1: exact matches. Each output fact can be used once.
    pairs = {}
    used = set()
    for ki, key in enumerate(key_facts):
        candidates = [
            oi for oi, out in enumerate(out_facts)
            if oi not in used
            and out["type"] == key["type"]
            and _name(out) == _name(key)
            and out["status"] == key["status"]
        ]
        if not candidates:
            continue
        # Prefer a candidate with the correct dose; otherwise take the first in file order.
        best = next((oi for oi in candidates if dose_correct(key, out_facts[oi]) is True), candidates[0])
        pairs[ki] = best
        used.add(best)

    # Step 2: wrong status. An unmatched key fact pairs with an unused output of the same type and name.
    wrong = {}
    for ki, key in enumerate(key_facts):
        if ki in pairs:
            continue
        for oi, out in enumerate(out_facts):
            if (oi not in used and out["type"] == key["type"] and _name(out) == _name(key)
                    and out["status"] != key["status"]):
                wrong[ki] = oi
                used.add(oi)
                break

    # Step 3: whatever output is still unused is a duplicate or a plain false alarm.
    matched_signatures = {
        (out_facts[oi]["type"], _name(out_facts[oi]), out_facts[oi]["status"]) for oi in pairs.values()
    }
    duplicates, false_alarms = set(), set()
    for oi, out in enumerate(out_facts):
        if oi in used:
            continue
        signature = (out["type"], _name(out), out["status"])
        if signature in matched_signatures:
            duplicates.add(oi)
        else:
            false_alarms.add(oi)
    return pairs, wrong, duplicates, false_alarms


def _conflict_shown(ki, key_facts, pairs, out_facts):
    """True only if this key fact and every other fact in its conflict group are matched,
    and each matched output fact carries the conflict flag."""
    key = key_facts[ki]
    group = key.get("conflict_group")
    if "conflict" not in key["flags"] or not group:
        return False
    for kj, other in enumerate(key_facts):
        if other.get("conflict_group") != group:
            continue
        if kj not in pairs:
            return False
        if "conflict" not in out_facts[pairs[kj]]["flags"]:
            return False
    return True


def _problem(patient_id, kind, key=None, out=None, duplicate=False):
    """One row for failures.csv: a missed case, a wrong status, or a false alarm, with its quote."""
    fact = key if key is not None else out
    return {
        "patient_id": patient_id,
        "kind": kind,
        "fact_id": fact["fact_id"],
        "type": fact["type"],
        "name": fact.get("name"),
        "key_status": key["status"] if key is not None else None,
        "output_status": out["status"] if out is not None else None,
        "key_critical": is_critical(key) if key is not None else None,
        "output_critical": is_critical(out) if out is not None else None,
        "duplicate": duplicate,
        "key_quote": key.get("quote") if key is not None else None,
        "output_quote": out.get("quote") if out is not None else None,
    }


def score_patient(compiled, key):
    """Score one patient's compiled record against their answer key.

    Returns {"counts": {"all": {...}, "critical": {...}}, "problems": [...]}.
    Each counts dict has every field in COUNT_FIELDS. problems lists each missed case,
    wrong status and false alarm, with the quote it came from.
    """
    if compiled["patient_id"] != key["patient_id"]:
        raise ValueError(f"compiled record is {compiled['patient_id']} but key is {key['patient_id']}")
    patient_id = key["patient_id"]
    key_facts = key["facts"]
    out_facts = compiled["facts"]
    pairs, wrong, duplicates, false_alarms = _match(key_facts, out_facts)

    counts = {scope: dict.fromkeys(COUNT_FIELDS, 0) for scope in SCOPES}

    def bump(field, critical, n=1):
        """Add n to a count for all facts, and also for critical facts if critical is True."""
        counts["all"][field] += n
        if critical:
            counts["critical"][field] += n

    problems = []

    # Walk the key facts. Each one is counted once, by its own criticality.
    for ki, key_fact in enumerate(key_facts):
        key_crit = is_critical(key_fact)
        bump("key_facts", key_crit)
        if "conflict" in key_fact["flags"]:
            bump("conflict_facts", key_crit)
            if _conflict_shown(ki, key_facts, pairs, out_facts):
                bump("conflict_shown", key_crit)

        if ki in pairs:
            out = out_facts[pairs[ki]]
            bump("matched", key_crit)
            if key_fact["type"] == "medicine":
                correct = dose_correct(key_fact, out)
                if correct is None:
                    bump("dose_not_applicable", key_crit)
                elif correct:
                    bump("dose_correct", key_crit)
                else:
                    bump("dose_wrong", key_crit)
        elif ki in wrong:
            # Wrong status: a missed case on the key side, and a false alarm on the output side.
            out = out_facts[wrong[ki]]
            out_crit = is_critical(out)
            bump("missed", key_crit)
            bump("wrong_status", out_crit)
            bump("false_alarms", out_crit)
            problems.append(_problem(patient_id, "wrong_status", key_fact, out))
        else:
            bump("missed", key_crit)
            problems.append(_problem(patient_id, "missed", key_fact))

    # Walk the output facts. Every output fact counts once, by its own criticality.
    for oi, out in enumerate(out_facts):
        out_crit = is_critical(out)
        bump("output_facts", out_crit)
        if oi in duplicates:
            bump("duplicates", out_crit)
            bump("false_alarms", out_crit)
            problems.append(_problem(patient_id, "false_alarm", out=out, duplicate=True))
        elif oi in false_alarms:
            bump("false_alarms", out_crit)
            problems.append(_problem(patient_id, "false_alarm", out=out))

    return {"counts": counts, "problems": problems}


def _sum_counts(results):
    """Add up the counts of many patients, for each scope."""
    totals = {scope: dict.fromkeys(COUNT_FIELDS, 0) for scope in SCOPES}
    for result in results:
        for scope in SCOPES:
            for field in COUNT_FIELDS:
                totals[scope][field] += result["counts"][scope][field]
    return totals


def _ratio(top, bottom):
    """A rate as a number from 0 to 1, rounded to 3 places. Blank when the denominator is zero."""
    if bottom == 0:
        return ""
    return round(top / bottom, 3)


def _load_ages_and_sex(patient_ids):
    """Read age band and sex for the given IDs from patients.csv.
    The demo patient is not in the split, so it is not found here."""
    found = {}
    with open(PATIENTS_CSV, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["patient_id"] in patient_ids:
                found[row["patient_id"]] = (row["age_band"], row["sex"])
    return found


def _check_allowed(patient_ids, include_heldout):
    """Refuse held-out and reserve IDs unless --include-heldout is given. Runs before any file is opened."""
    for pid in patient_ids:
        if pid == DEMO_ID or WORKING_RE.match(pid):
            continue
        if include_heldout and ANY_SPLIT_ID_RE.match(pid):
            continue
        raise SystemExit(
            f"{pid} is not a working or demo patient. Held-out and reserve IDs need --include-heldout."
        )


def _find_key(keys_dir, pid):
    """Find <ID>_key.json directly in keys_dir, or inside keys_dir/<ID>/."""
    for path in (keys_dir / f"{pid}_key.json", keys_dir / pid / f"{pid}_key.json"):
        if path.exists():
            return path
    raise FileNotFoundError(f"no answer key for {pid} in {keys_dir}")


def _per_patient_fields():
    """Column names for per_patient.csv: each count, for all facts and then for critical facts."""
    fields = ["patient_id", "age_band", "sex"]
    for field in COUNT_FIELDS:
        for scope in SCOPES:
            fields.append(f"{field}_{scope}")
    return fields


def _write_csv(path, fieldnames, rows):
    """Write rows to a UTF-8 CSV file with a header row."""
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    """Score the given patients and write per_patient.csv, summary.csv and failures.csv."""
    parser = argparse.ArgumentParser(description="Score compiled records against answer keys (T18).")
    parser.add_argument("--compiled-dir", type=Path, required=True, help="folder of <ID>.json compiled records")
    parser.add_argument("--keys-dir", type=Path, required=True, help="folder of <ID>_key.json answer keys")
    parser.add_argument("--patients", nargs="+", required=True, metavar="ID", help="patient IDs to score")
    parser.add_argument("--out-dir", type=Path, required=True, help="folder to write the CSV files into")
    parser.add_argument("--include-heldout", action="store_true",
                        help="allow held-out and reserve IDs (only after the freeze, T36)")
    args = parser.parse_args(argv)

    patient_ids = list(dict.fromkeys(args.patients))  # keep order, drop repeats
    _check_allowed(patient_ids, args.include_heldout)

    ages = _load_ages_and_sex(set(patient_ids))
    results = []
    rows = []
    failure_rows = []
    for pid in patient_ids:
        compiled = load_json(args.compiled_dir / f"{pid}.json")
        key = load_json(_find_key(args.keys_dir, pid))
        result = score_patient(compiled, key)
        results.append(result)

        if pid in ages:
            age_band, sex = ages[pid]
        else:
            age_band, sex = "", ""
            print(f"warning: {pid} is not in patients.csv; age_band and sex left blank", file=sys.stderr)

        row = {"patient_id": pid, "age_band": age_band, "sex": sex}
        for scope in SCOPES:
            for field in COUNT_FIELDS:
                row[f"{field}_{scope}"] = result["counts"][scope][field]
        rows.append(row)
        failure_rows.extend(result["problems"])

    # Totals are summed from the counts, then recall and precision are worked out from the totals.
    totals = _sum_counts(results)
    summary_rows = []
    for scope in SCOPES:
        counts = totals[scope]
        summary_rows.append({
            "scope": scope,
            "patients": len(patient_ids),
            **counts,
            "recall": _ratio(counts["matched"], counts["key_facts"]),
            "precision": _ratio(counts["matched"], counts["output_facts"]),
        })

    args.out_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(args.out_dir / "per_patient.csv", _per_patient_fields(), rows)
    _write_csv(args.out_dir / "summary.csv",
               ["scope", "patients"] + COUNT_FIELDS + ["recall", "precision"], summary_rows)
    _write_csv(args.out_dir / "failures.csv",
               ["patient_id", "kind", "fact_id", "type", "name", "key_status", "output_status",
                "key_critical", "output_critical", "duplicate", "key_quote", "output_quote"],
               failure_rows)

    print(f"Scored {len(patient_ids)} patient(s): {', '.join(patient_ids)}")
    for summary in summary_rows:
        print(f"{summary['scope']:>8}: key {summary['key_facts']}, output {summary['output_facts']}, "
              f"matched {summary['matched']}, missed {summary['missed']}, "
              f"false alarms {summary['false_alarms']}, wrong status {summary['wrong_status']}, "
              f"duplicates {summary['duplicates']}, recall {summary['recall']}, precision {summary['precision']}")
    print(f"Wrote {args.out_dir / 'per_patient.csv'}, {args.out_dir / 'summary.csv'}, "
          f"{args.out_dir / 'failures.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
