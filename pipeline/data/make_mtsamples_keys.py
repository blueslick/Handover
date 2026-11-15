"""Make the answer keys for the 12 MTSamples notes (T43) from the hand labels.

Reads pipeline/data/mtsamples/t43_labels.csv (the labels tab of the command centre, saved as
CSV) and pipeline/data/mtsamples/id_map.csv (M001 -> D201 ... M012 -> D212). Writes one key per
note to pipeline/data/demo/D2xx/D2xx_key.json, in the same shape as demo/D001/D001_key.json.

The labels are not changed here. Only the format conversions below are made:

  * One label row = one key fact, in sheet order. Facts are numbered D2xx-F01, F02 ... per note.
  * name_as_written: the Name as written, with end spaces removed.
  * name: the Generic name, lowercase, end spaces removed. None for "none_recorded" rows.
  * A row with a blank Generic name that is not "none_recorded" is LEFT OUT (the format needs
    a name). Those rows are listed in the report.
  * dose: tidied to "number unit" (e.g. "500mg" -> "500 mg", "1g " -> "1 g"). Only units in
    shared/fixed_lists.json "dose_units" are allowed. Anything that does not fit becomes null
    and is listed in the report. A number or unit is never guessed.
  * frequency: How often, or null if blank. Must be on the fixed list, or the script stops.
  * reaction: Reaction with end spaces removed, or null.
  * status: Status as written. Must be allowed for its type in fixed_lists.json, or the script
    stops and reports (it does not fix it).
  * Fixed for every fact: hospital "B", date null, quote null (the labels have no quotes),
    sources = one entry for this note, history [], conflict_group null.
  * flags: empty, except "missing_dose" on a current medicine with no dose. The format
    requires that flag (shared/validate.py), so it is added, not judged.

Run it (no model calls, no network):

    .venv/bin/python pipeline/data/make_mtsamples_keys.py

It prints the report. Then check each file with: .venv/bin/python shared/validate.py <key file>
"""
import csv
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "pipeline" / "data"
MTS = DATA / "mtsamples"
LABELS = MTS / "t43_labels.csv"
ID_MAP = MTS / "id_map.csv"
LISTS = REPO / "shared" / "fixed_lists.json"
DEMO = DATA / "demo"

# The allowed units, frequencies and statuses (shared/fixed_lists.json).
LISTS_JSON = json.loads(LISTS.read_text(encoding="utf-8"))
DOSE_UNITS = set(LISTS_JSON["dose_units"])
FREQUENCIES = set(LISTS_JSON["frequencies"])
STATUSES_BY_TYPE = LISTS_JSON["statuses_allowed_by_type"]
DOSE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)([A-Za-z]+)")   # e.g. "500mg", "1g", "0.2mg", "50units"


def tidy_dose(text):
    """Return (dose, ok). dose is "number unit" with an allowed unit, or None when the text
    does not fit the format. ok is False when a non-blank dose was set to null.
    Nothing is guessed."""
    text = (text or "").strip()
    if not text:
        return None, True                                    # blank dose: not stated, not a problem
    m = DOSE_PATTERN.fullmatch(re.sub(r"\s+", "", text))     # spaces are ignored: "1 g" and "1g" both match
    if m is None:
        return None, False                                   # e.g. "20" (no unit), "70 units / 6 units times 4 years"
    number, unit = m.group(1), m.group(2)
    if unit not in DOSE_UNITS:
        return None, False                                   # e.g. "mEq": not an allowed unit
    return f"{number} {unit}", True


def clean(value):
    """End spaces removed; a blank cell is None."""
    value = (value or "").strip()
    return value or None


def read_rows():
    """All label rows, in sheet order, with the sheet line number for the report."""
    rows = []
    with open(LABELS, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)                          # quoted cells, including line breaks, are handled
        reader.fieldnames                                    # read the header first, so line counts start right
        while True:
            before = reader.line_num                         # physical lines read so far (line 1 = header)
            try:
                row = next(reader)
            except StopIteration:
                break
            rows.append((before + 1, row))                   # physical line where this row starts
    return rows


def read_id_map():
    """The M-to-D mapping, e.g. {'M001': 'D201', ...}."""
    with open(ID_MAP, encoding="utf-8", newline="") as fh:
        return {row["mtsamples_id"].strip(): row["demo_id"].strip() for row in csv.DictReader(fh)}


def build_key(demo_id, rows, left_out, dose_nulls):
    """One answer key for one note. Adds to left_out and dose_nulls for the report."""
    facts = []
    for sheet_row, row in rows:
        ftype = clean(row["Type"])
        status = clean(row["Status"])
        name_as_written = clean(row["Name as written"])
        generic = clean(row["Generic name"])
        # Stop if the labels use a type or status the format does not allow.
        if ftype not in STATUSES_BY_TYPE:
            raise SystemExit(f"STOP: sheet line {sheet_row} ({demo_id}): unknown type '{ftype}'. Nothing was written.")
        if status not in STATUSES_BY_TYPE[ftype]:
            raise SystemExit(f"STOP: sheet line {sheet_row} ({demo_id}): status '{status}' is not allowed for "
                             f"{ftype}. Reported, not fixed. Nothing was written.")
        frequency = clean(row["How often"])
        if frequency is not None and frequency not in FREQUENCIES:
            raise SystemExit(f"STOP: sheet line {sheet_row} ({demo_id}): frequency '{frequency}' is not on the "
                             "fixed list. Reported, not fixed. Nothing was written.")
        # A "none recorded" row has no drug name. Any other row needs a generic name, or it is left out.
        if status != "none_recorded" and generic is None:
            left_out.append((demo_id, sheet_row, ftype, name_as_written))
            continue
        name = None if status == "none_recorded" else generic.lower()
        dose_raw = clean(row["Dose"])
        dose, ok = tidy_dose(dose_raw)
        if not ok:
            dose_nulls.append((demo_id, sheet_row, dose_raw))
        if ftype != "medicine":
            dose, frequency = None, None                     # dose and frequency belong to medicines only
        n = len(facts) + 1
        facts.append({
            "fact_id": f"{demo_id}-F{n:02d}",
            "patient_id": demo_id,
            "type": ftype,
            "name": name,
            "name_as_written": name_as_written,
            "dose": dose,
            "frequency": frequency,
            "reaction": clean(row["Reaction"]) if ftype == "allergy" else None,
            "status": status,
            "hospital": "B",
            "date": None,
            "quote": None,
            "sources": [{"hospital": "B", "date": None, "quote": None, "file": f"{demo_id}_B.txt"}],
            "history": [],
            "conflict_group": None,
            # Format rule (shared/validate.py): a current medicine with no dose carries missing_dose.
            "flags": ["missing_dose"] if (ftype == "medicine" and status == "current" and dose is None) else [],
        })
    return {
        "format_version": "1.0",
        "kind": "answer_key",
        "patient_id": demo_id,
        "run_id": None,
        "built_from": [f"{demo_id}_B.txt"],
        "facts": facts,
    }


def main():
    id_map = read_id_map()
    rows = read_rows()
    unknown = sorted({r["Note"].strip() for _, r in rows} - set(id_map))
    if unknown:
        raise SystemExit(f"STOP: labels name notes not in id_map.csv: {', '.join(unknown)}. Nothing was written.")

    left_out, dose_nulls, written = [], [], []
    for mts_id, demo_id in id_map.items():
        note_rows = [(i, r) for i, r in rows if r["Note"].strip() == mts_id]
        key = build_key(demo_id, note_rows, left_out, dose_nulls)
        out = DEMO / demo_id / f"{demo_id}_key.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(key, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append((mts_id, demo_id, len(key["facts"]), out))

    print(f"Label rows read: {len(rows)}. Notes: {len(id_map)}.")
    print(f"{'note':<6}{'demo':<6}{'key facts':>10}   file")
    for mts_id, demo_id, n, out in written:
        print(f"{mts_id:<6}{demo_id:<6}{n:>10}   {out.relative_to(REPO)}")
    total = sum(n for _, _, n, _ in written)
    print(f"Total key facts: {total} (from {len(rows)} label rows; {len(left_out)} left out)")

    print(f"\nLeft out ({len(left_out)}): a blank Generic name, and not 'none recorded'")
    for demo_id, sheet_row, ftype, name in left_out:
        print(f"  {demo_id} sheet line {sheet_row}: {ftype} '{name}'")
    print(f"\nDoses set to null, because they do not fit the format ({len(dose_nulls)}):")
    for demo_id, sheet_row, dose in dose_nulls:
        print(f"  {demo_id} sheet line {sheet_row}: '{dose}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
