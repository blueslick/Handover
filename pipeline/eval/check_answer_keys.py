# T33: check each saved answer key against the raw Synthea tables.
#
# What it does, in plain words:
#   1. Maps each patient ID to its Synthea patient using pipeline/data/patients.csv.
#   2. Reads that patient's raw Synthea allergies and medications (the CSV tables
#      in pipeline/data/synthea_raw/csv/). It does NOT use the trimmed *_synthea.json
#      files or the answer-key script's code, so this check stays independent.
#   3. Reads the saved answer key (pipeline/data/<split>/<ID>/<ID>_key.json).
#   4. Compares the two and reports four kinds of mismatch:
#        - allergy in Synthea, not in the key
#        - allergy in the key, not in Synthea
#        - medicine in Synthea, not in the key (split into current and stopped)
#        - medicine in the key, not in Synthea
#      and one more: a medicine in both whose status (current vs stopped) differs.
#
# Run from anywhere (paths are built from this file's location):
#   .venv/bin/python pipeline/eval/check_answer_keys.py                  # counts only
#   .venv/bin/python pipeline/eval/check_answer_keys.py --only P001,P002  # test mode
#   .venv/bin/python pipeline/eval/check_answer_keys.py --details <path>  # also write the detail file
#
# Output:
#   - Console: counts for each split. Per-patient lines are printed for working
#     patients only, because held-out contents must not be shown in a session run by Daniel.
#   - File (only if --details is given): every patient's details as JSON. It contains
#     held-out facts. Write it OUTSIDE the repo (for example in the scratchpad), and never
#     stage or commit it.
#
# Only standard-library modules are used, so no new package is needed. Every file is
# read as UTF-8.

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

# Folder paths, built from this file's location (no absolute paths).
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "pipeline" / "data"
SYNTHEA = DATA / "synthea_raw" / "csv"
SHARED = ROOT / "shared"
ENC = "utf-8"

# Each split: the folder that holds its keys, and the ID list it should match.
SPLITS = {
    "working": {"folder": "working", "ids": "working_ids.txt"},
    "heldout": {"folder": "heldout", "ids": "heldout_ids.txt"},
    "reserve": {"folder": "reserve", "ids": "heldout_ext_ids.txt"},
}

# Words Synthea adds around a drug name (strengths, pack sizes, forms, routes).
# They are dropped when reading a Synthea medication name.
FORM_WORDS = {
    "mg", "ml", "mcg", "hr", "actuat", "day", "pack", "per", "unt", "oral", "tablet",
    "tablets", "capsule", "capsules", "injection", "injectable", "solution", "inhaler",
    "metered", "dose", "transdermal", "system", "mucosal", "spray", "topical", "cream",
    "extended", "release", "chewable", "vaginal", "ring", "intrauterine", "prefilled",
    "syringe", "drug", "implant", "auto-injector", "suspension", "film",
    # Added after the first run: release and form words, and the species word in insulin names.
    "human", "delayed", "dry", "powder", "abuse-deterrent", "modified",
}

# Salt and ester words the key leaves off (for example "hydrochloride" in
# "oxycodone hydrochloride" is written "oxycodone" in the key).
SALT_WORDS = {
    "hydrochloride", "hydrocholoride", "hydrochlorid", "bitartrate", "hydrobromide",
    "maleate", "acetate", "propionate", "succinate", "sodium", "potassium",
    "hyclate", "phosphate",
}

# The key only covers each patient's Synthea history from the 5 years before the
# reference date (18 Nov 2021). The trim script's header comment (T11) sets this window.
# It is restated here, not imported, so this check does not depend on the trim code.
# A medicine row counts only if it overlaps the window. Allergies have no stop date,
# so they are not filtered.
WINDOW_START = date(2016, 11, 18)
WINDOW_END = date(2021, 11, 18)

# Spelling and naming differences between Synthea and the key that the brand table
# does not already cover. Keys are lowercase whole names; values are the key's spelling.
ALIASES = {
    "mold": "mould",
    "eggs": "egg",
    "tree nut": "tree nuts",
    "soya bean": "soya",
    "sulfamethoxazole / trimethoprim": "co-trimoxazole",
    "penicillin v": "penicillin",
    "cyclosporine": "ciclosporin",
}


def norm_order(text: str) -> str:
    """Sort the words of a name, so 'Regular Insulin' and 'insulin regular' match."""
    return " ".join(sorted(text.split()))


def read_csv(path: Path) -> list[dict]:
    """Read a CSV file as a list of row dictionaries (UTF-8)."""
    with open(path, encoding=ENC, newline="") as f:
        return list(csv.DictReader(f))


def load_brands() -> dict[str, str]:
    """Load brand -> generic from the shared brand table, lowercased."""
    rows = read_csv(SHARED / "brand_to_generic.csv")
    return {r["brand"].strip().lower(): r["generic"].strip().lower() for r in rows}


def load_drug_names() -> set[str]:
    """Load every name in the shared drug list, lowercased and word-sorted like canon() output (used only to flag unknown names)."""
    rows = read_csv(SHARED / "drug_list.csv")
    return {norm_order(r["name"].strip().lower()) for r in rows}


def strip_salts(text: str) -> str:
    """Remove salt or ester words from the end of a name, e.g. 'oxycodone hydrochloride'."""
    words = text.split()
    while words and words[-1] in SALT_WORDS:
        words.pop()
    return " ".join(words)


def canon(name: str, brands: dict[str, str]) -> frozenset[str]:
    """Turn a drug or allergy name into a set of plain lowercase ingredient names.

    Brand names become generics, salt words are dropped, spellings are aligned, and
    a combination such as 'amoxicillin / clavulanate' becomes two ingredients. Both
    the Synthea side and the key side go through this same function.
    """
    s = " ".join(name.lower().split())
    # Whole-name aliases first, so a pair like sulfamethoxazole / trimethoprim
    # is treated as one thing.
    if s in ALIASES:
        return frozenset([norm_order(ALIASES[s])])
    # A brand name may map to a combination, so look it up before splitting.
    if s in brands:
        s = brands[s]
    out: set[str] = set()
    for part in s.split("/"):
        p = strip_salts(part.strip())
        if p in brands:
            p = brands[p]
        for sub in p.split("/"):
            # Drop salt words, apply the spelling aliases (on the words as written),
            # then sort the words so word order does not matter.
            sub = strip_salts(sub.strip())
            if not sub:
                continue
            sub = ALIASES.get(sub, sub)
            out.add(norm_order(sub))
    return frozenset(out)


def in_window(start: str, stop: str) -> bool:
    """True if a Synthea row (ISO start and stop, stop may be blank) overlaps the 5-year window."""
    start_d = date.fromisoformat(start[:10])
    if start_d > WINDOW_END:
        return False
    if stop.strip() == "":
        # No stop date: still active, so it overlaps the window.
        return True
    return date.fromisoformat(stop[:10]) >= WINDOW_START


def synthea_med_names(description: str) -> list[str]:
    """Pull the drug names out of a Synthea medication description.

    Example: 'amLODIPine 2.5 MG Oral Tablet' gives ['amLODIPine'];
    'Acetaminophen 325 MG / Oxycodone Hydrochloride 10 MG Oral Tablet [Percocet]'
    gives ['Acetaminophen', 'Oxycodone Hydrochloride'].
    """
    # Drop any [brand] tag at the end, since the name before it is already the ingredient.
    text = re.sub(r"\[[^\]]*\]", " ", description)
    groups: list[list[str]] = [[]]
    for tok in text.split():
        if tok == "/":
            # A slash between two words separates two ingredients.
            groups.append([])
            continue
        low = tok.lower()
        # Skip anything with a digit (strengths, pack sizes, codes) and unit pairs such as MG/ML.
        if any(c.isdigit() for c in tok) or low in FORM_WORDS or re.fullmatch(r"[a-z]+/[a-z]+", low):
            continue
        groups[-1].append(tok)
    return [" ".join(g) for g in groups if g]


def synthea_med_items(description: str, brands: dict[str, str]) -> frozenset[str]:
    """All ingredient names in one Synthea medication row."""
    items: set[str] = set()
    for name in synthea_med_names(description):
        items |= canon(name, brands)
    return frozenset(items)


def synthea_allergy_item(description: str, brands: dict[str, str]) -> frozenset[str]:
    """The ingredient set for one Synthea allergy row, dropping (substance) / (organism) tags."""
    cleaned = re.sub(r"\([^)]*\)", " ", description)
    return canon(cleaned, brands)


def fs_list(items: frozenset[str]) -> list[str]:
    """Sorted list for writing to JSON."""
    return sorted(items)


def check_patient(pid, split, synthea_id, allergy_rows, med_rows, brands, drug_names) -> dict:
    """Compare one patient's answer key with that patient's raw Synthea rows."""
    # Load the saved answer key for this patient.
    key_path = DATA / SPLITS[split]["folder"] / pid / f"{pid}_key.json"
    with open(key_path, encoding=ENC) as f:
        key = json.load(f)
    facts = key["facts"]

    # Synthea allergies: each row is an active allergy (Synthea has no stop date for them).
    synth_allergy: dict[frozenset, list[str]] = {}
    for r in allergy_rows:
        item = synthea_allergy_item(r["DESCRIPTION"], brands)
        synth_allergy.setdefault(item, []).append(r["DESCRIPTION"])

    # Key allergies: skip "no known allergies" (name is null).
    key_allergy: dict[frozenset, str] = {}
    for f in facts:
        if f["type"] == "allergy" and f["name"] is not None:
            key_allergy.setdefault(canon(f["name"], brands), f["status"])

    # Synthea medicines: a row with no stop date is current; a medicine is current if any row is open.
    synth_med: dict[frozenset, dict] = {}
    unparsed_meds: list[str] = []
    outside_window = 0
    for r in med_rows:
        # Rows that ended before the 5-year window are out of scope, so they are counted, not compared.
        if not in_window(r["START"], r["STOP"]):
            outside_window += 1
            continue
        item = synthea_med_items(r["DESCRIPTION"], brands)
        if not item:
            unparsed_meds.append(r["DESCRIPTION"])
            continue
        entry = synth_med.setdefault(item, {"status": "stopped", "raw": []})
        if r["STOP"].strip() == "":
            entry["status"] = "current"
        entry["raw"].append(r["DESCRIPTION"])

    # Key medicines: skip "no regular medicines" (name is null).
    key_med: dict[frozenset, list[dict]] = {}
    for f in facts:
        if f["type"] == "medicine" and f["name"] is not None:
            key_med.setdefault(canon(f["name"], brands), []).append(
                {"status": f["status"], "name_as_written": f["name_as_written"]}
            )

    # Allergy comparison.
    allergy_missing = [
        {"item": fs_list(s), "synthea_text": synth_allergy[s]}
        for s in synth_allergy if s not in key_allergy
    ]
    allergy_extra = [
        {"item": fs_list(s), "key_status": st}
        for s, st in key_allergy.items() if s not in synth_allergy
    ]

    # Medicine comparison: presence, then status when both sides have the medicine.
    med_missing_current, med_missing_stopped = [], []
    for s, e in synth_med.items():
        if s not in key_med:
            rec = {"item": fs_list(s), "synthea_status": e["status"], "synthea_text": e["raw"]}
            (med_missing_current if e["status"] == "current" else med_missing_stopped).append(rec)
    med_extra = [
        {"item": fs_list(s), "key_status": [k["status"] for k in ks], "name_as_written": [k["name_as_written"] for k in ks]}
        for s, ks in key_med.items() if s not in synth_med
    ]
    status_mismatch, not_comparable = [], []
    for s, ks in key_med.items():
        if s not in synth_med:
            continue
        synth_status = synth_med[s]["status"]
        for k in ks:
            if k["status"] in ("current", "stopped"):
                if k["status"] != synth_status:
                    status_mismatch.append({
                        "item": fs_list(s), "key_status": k["status"],
                        "synthea_status": synth_status, "synthea_text": synth_med[s]["raw"],
                    })
            else:
                # For example "planned": Synthea cannot show a planned medicine, so it is not checked.
                not_comparable.append({"item": fs_list(s), "key_status": k["status"]})

    # Names in Synthea that are not in the shared drug list: a mapping gap to check by hand.
    all_synth_items = set(synth_allergy) | set(synth_med)
    names_not_in_list = sorted(
        ing for s in all_synth_items for ing in s if ing not in drug_names
    )

    return {
        "patient_id": pid,
        "split": split,
        "synthea_id": synthea_id,
        "key_file": str(key_path.relative_to(ROOT)),
        "key_fact_count": len(facts),
        "unparsed_synthea_medicine_rows": unparsed_meds,
        "medicine_rows_outside_window": outside_window,
        "allergy": {
            "synthea": [fs_list(s) for s in synth_allergy],
            "key": [fs_list(s) for s in key_allergy],
            "missing_from_key": allergy_missing,
            "extra_in_key": allergy_extra,
        },
        "medicine": {
            "missing_from_key_current": med_missing_current,
            "missing_from_key_stopped": med_missing_stopped,
            "extra_in_key": med_extra,
            "status_mismatch": status_mismatch,
            "not_comparable_key_status": not_comparable,
        },
        "names_not_in_drug_list": names_not_in_list,
    }


def count_patient(detail: dict, totals: Counter, patients_with: Counter) -> None:
    """Add one patient's counts to the split totals."""
    a = detail["allergy"]
    m = detail["medicine"]
    counts = {
        "allergy_missing_from_key": len(a["missing_from_key"]),
        "allergy_extra_in_key": len(a["extra_in_key"]),
        "medicine_missing_from_key_current": len(m["missing_from_key_current"]),
        "medicine_missing_from_key_stopped": len(m["missing_from_key_stopped"]),
        "medicine_extra_in_key": len(m["extra_in_key"]),
        "medicine_status_mismatch": len(m["status_mismatch"]),
        "medicine_not_comparable_key_status": len(m["not_comparable_key_status"]),
        "names_not_in_drug_list": len(detail["names_not_in_drug_list"]),
        "unparsed_synthea_medicine_rows": len(detail["unparsed_synthea_medicine_rows"]),
        "medicine_rows_outside_window (not compared)": detail["medicine_rows_outside_window"],
    }
    for k, v in counts.items():
        totals[k] += v
        if v:
            patients_with[k] += 1


def main() -> None:
    """Run the check for every patient (or the --only list) and print counts."""
    parser = argparse.ArgumentParser(description="Check answer keys against raw Synthea (T33).")
    parser.add_argument("--only", default="", help="comma-separated IDs for a quick test, e.g. P001,P002")
    parser.add_argument("--details", default="", help="path for the detail JSON (held-out facts; keep it outside the repo)")
    args = parser.parse_args()
    only = {x.strip() for x in args.only.split(",") if x.strip()}

    # Load the patient map and the raw Synthea tables for the patients in this check.
    patients = [r for r in read_csv(DATA / "patients.csv") if r["split"] in SPLITS]
    if only:
        patients = [r for r in patients if r["patient_id"] in only]
    wanted_sids = {r["synthea_id"] for r in patients}
    allergy_rows_all = read_csv(SYNTHEA / "allergies.csv")
    med_rows_all = read_csv(SYNTHEA / "medications.csv")
    synth_patient_ids = {r["Id"] for r in read_csv(SYNTHEA / "patients.csv")}

    # Group the raw rows by Synthea patient ID, keeping only the patients we need.
    allergy_by = {}
    for r in allergy_rows_all:
        if r["PATIENT"] in wanted_sids:
            allergy_by.setdefault(r["PATIENT"], []).append(r)
    med_by = {}
    for r in med_rows_all:
        if r["PATIENT"] in wanted_sids:
            med_by.setdefault(r["PATIENT"], []).append(r)

    brands = load_brands()
    drug_names = load_drug_names()

    # Coverage: always check all 180 patients from patients.csv (not just --only).
    # The split ID files hold Synthea IDs, so they are compared with the synthea_id column.
    all_patients = [r for r in read_csv(DATA / "patients.csv") if r["split"] in SPLITS]
    coverage = {}
    for split, spec in SPLITS.items():
        list_ids = [x.strip() for x in (DATA / "split" / spec["ids"]).read_text(encoding=ENC).splitlines() if x.strip()]
        split_rows = [r for r in all_patients if r["split"] == split]
        missing_key = [
            r["patient_id"] for r in split_rows
            if not (DATA / spec["folder"] / r["patient_id"] / f"{r['patient_id']}_key.json").exists()
        ]
        coverage[split] = {
            "id_list_count": len(list_ids),
            "patients_csv_count": len(split_rows),
            "ids_match_patients_csv": set(list_ids) == {r["synthea_id"] for r in split_rows},
            "key_files_found": len(split_rows) - len(missing_key),
            "missing_key_ids": missing_key,
        }

    # Run the comparison for each patient.
    details = []
    totals: dict[str, Counter] = {s: Counter() for s in SPLITS}
    patients_with: dict[str, Counter] = {s: Counter() for s in SPLITS}
    sid_problems = []
    for p in patients:
        pid, sid, split = p["patient_id"], p["synthea_id"], p["split"]
        if sid not in synth_patient_ids:
            sid_problems.append(pid)
            continue
        detail = check_patient(pid, split, sid, allergy_by.get(sid, []), med_by.get(sid, []), brands, drug_names)
        details.append(detail)
        count_patient(detail, totals[split], patients_with[split])

    # Write the full detail file only when a path is given (held-out details; keep it outside the repo).
    if args.details:
        with open(Path(args.details), "w", encoding=ENC) as f:
            json.dump({"coverage": coverage, "patients": details}, f, indent=2, ensure_ascii=False)
        print(f"Detail file written to: {args.details} (held-out facts; not for the repo)")

    # Console output: counts for every split; per-patient lines for working patients only.
    print(f"Synthea IDs not found: {len(sid_problems)}")
    for split in SPLITS:
        cov = coverage[split]
        print(f"\n== {split}: key files found {cov['key_files_found']} of {cov['patients_csv_count']} "
              f"(ID list has {cov['id_list_count']}; matches patients.csv: {cov['ids_match_patients_csv']})")
        if cov["missing_key_ids"]:
            print(f"   missing key files: {', '.join(cov['missing_key_ids'])}" if split == "working" else
                  f"   missing key files: {len(cov['missing_key_ids'])} (IDs not listed here; held-out)")
        t = totals[split]
        pw = patients_with[split]
        for k in sorted(t):
            print(f"   {k}: {t[k]} items in {pw[k]} patients")
        n_patients = sum(1 for d in details if d["split"] == split)
        print(f"   patients checked: {n_patients}")

    # Working patients only: show each patient's mismatches so they can be checked by hand.
    for d in details:
        if d["split"] != "working":
            continue
        a, m = d["allergy"], d["medicine"]
        lines = []
        for x in a["missing_from_key"]:
            lines.append(f"    allergy in Synthea, not in key: {x['item']} (Synthea text: {x['synthea_text']})")
        for x in a["extra_in_key"]:
            lines.append(f"    allergy in key, not in Synthea: {x['item']} (key status {x['key_status']})")
        for x in m["missing_from_key_current"]:
            lines.append(f"    medicine CURRENT in Synthea, not in key: {x['item']} ({x['synthea_text']})")
        for x in m["missing_from_key_stopped"]:
            lines.append(f"    medicine stopped in Synthea, not in key: {x['item']} ({x['synthea_text']})")
        for x in m["extra_in_key"]:
            lines.append(f"    medicine in key, not in Synthea: {x['item']} (key {x['key_status']}, written {x['name_as_written']})")
        for x in m["status_mismatch"]:
            lines.append(f"    medicine status differs: {x['item']} key={x['key_status']} Synthea={x['synthea_status']} ({x['synthea_text']})")
        if lines:
            print(f"\n{d['patient_id']}:")
            print("\n".join(lines))


if __name__ == "__main__":
    main()
