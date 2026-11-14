"""Validate Handover JSON files against the shared record format (v1.0).

Usage:
    python shared/validate.py outputs/compiled/<run_id>/P001.json [more files...]
    python shared/validate.py --kind extracted outputs/extracted/<run_id>/P001_A.json

Checks the JSON Schema, then the cross-field rules that a schema can't express.
Exits 1 if any file fails. Needs: pip install jsonschema
"""
import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

SHARED = Path(__file__).resolve().parent
LISTS = json.loads((SHARED / "fixed_lists.json").read_text(encoding="utf-8"))
ALLOWED = LISTS["statuses_allowed_by_type"]


def rule_errors(fact, compiled):
    errs = []
    t, s = fact["type"], fact["status"]
    if s not in ALLOWED[t]:
        errs.append(f"status '{s}' not allowed for type '{t}'")
    if (fact["name"] is None) != (s == "none_recorded") and not (
        fact["name"] is None and "unknown_name" in fact["flags"]
    ):
        errs.append("name must be null exactly when status is none_recorded (or name is unknown)")
    if t != "medicine" and (fact["dose"] or fact["frequency"]):
        errs.append("dose/frequency only allowed on medicine facts")
    if t != "allergy" and fact["reaction"]:
        errs.append("reaction only allowed on allergy facts")
    if t == "medicine" and s == "current" and not fact["dose"] and "missing_dose" not in fact["flags"]:
        errs.append("current medicine with no dose must carry the missing_dose flag")
    if fact["name"] is not None and fact["name"] != fact["name"].lower():
        errs.append("name must be lowercase generic")
    if compiled:
        has_group = fact["conflict_group"] is not None
        if has_group != ("conflict" in fact["flags"]):
            errs.append("conflict flag and conflict_group must appear together")
        if "dose_changed" in fact["flags"] and not fact["history"]:
            errs.append("dose_changed needs the earlier dose in history")
    return errs


def check_file(path, kind):
    schema = json.loads((SHARED / "schema" / f"{kind}.schema.json").read_text(encoding="utf-8"))
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    problems = [f"schema: {'/'.join(map(str, e.path))}: {e.message}"
                for e in Draft202012Validator(schema).iter_errors(doc)]
    if problems:
        return problems  # cross-field checks assume a schema-valid doc
    compiled = kind == "compiled"
    ids, groups = set(), {}
    for i, fact in enumerate(doc["facts"]):
        for e in rule_errors(fact, compiled):
            problems.append(f"facts[{i}]: {e}")
        if compiled:
            if fact["patient_id"] != doc["patient_id"]:
                problems.append(f"facts[{i}]: patient_id differs from file")
            if fact["fact_id"] in ids:
                problems.append(f"facts[{i}]: duplicate fact_id {fact['fact_id']}")
            ids.add(fact["fact_id"])
            if fact["conflict_group"]:
                groups.setdefault(fact["conflict_group"], []).append(i)
    for g, members in groups.items():
        if len(members) < 2:
            problems.append(f"conflict_group {g} has only one fact; a conflict needs both sides")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["compiled", "extracted"], default="compiled")
    ap.add_argument("files", nargs="+")
    args = ap.parse_args()
    failed = 0
    for f in args.files:
        probs = check_file(f, args.kind)
        print(f"{'OK  ' if not probs else 'FAIL'} {f}")
        for p in probs:
            print(f"     {p}")
        failed += bool(probs)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
