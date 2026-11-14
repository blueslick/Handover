"""Build the brand-to-generic table and the drug list (T15). Code only, no AI, no patient files.

Reads the two tables behind the hospital templates:

    pipeline/data/templates/medicine_table.csv   every medicine name the templates can write
    pipeline/data/templates/allergy_table.csv    every allergy name the templates can write

and writes:

    shared/brand_to_generic.csv   brand,generic
        Every brand Hospital C can write (medicines and drug allergies), plus the other
        names in the medicine table's also_known_as column (acetaminophen, albuterol,
        frusemide ...), each pointing to the generic name the answer key uses.
    shared/drug_list.csv          name,kind
        Every generic medicine name (kind medicine; combination medicines appear whole,
        e.g. "paracetamol / codeine", and each part also appears on its own), and every
        allergy name (kind allergy). A name can appear once per kind (ibuprofen is both).

Because it reads the template tables and not the patient folders, held-out patients are
covered without anyone opening them.

The Check step (T22) should match brands ignoring capital letters ("glucophage" = "Glucophage").

    python pipeline/data/make_brand_table.py           write both files, then run the checks
    python pipeline/data/make_brand_table.py --check   checks only, writes nothing

The checks stop with an error if a name would point to two different generics, if any name
Hospital C can write would not turn into a generic, or if a row already in the files would be lost.
"""

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEDICINE_TABLE = ROOT / "pipeline" / "data" / "templates" / "medicine_table.csv"
ALLERGY_TABLE = ROOT / "pipeline" / "data" / "templates" / "allergy_table.csv"
BRAND_FILE = ROOT / "shared" / "brand_to_generic.csv"
DRUG_FILE = ROOT / "shared" / "drug_list.csv"


def read_rows(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build():
    medicines = read_rows(MEDICINE_TABLE)
    allergies = read_rows(ALLERGY_TABLE)

    brand_to_generic = {}   # lowercase brand -> (brand as written, generic)
    problems = []

    def add_brand(brand, generic, where):
        brand, generic = brand.strip(), generic.strip()
        if not brand or brand.lower() == generic.lower():
            return
        key = brand.lower()
        if key in brand_to_generic and brand_to_generic[key][1] != generic:
            problems.append(f"'{brand}' points to both '{brand_to_generic[key][1]}' and '{generic}' ({where})")
            return
        brand_to_generic.setdefault(key, (brand, generic))

    for row in medicines:
        add_brand(row["brand"], row["generic"], "medicine brand")
    for row in allergies:
        add_brand(row["brand"], row["name"], "allergy brand")
    for row in medicines:
        if row["also_known_as"]:
            add_brand(row["also_known_as"], row["generic"], "other name")

    drugs = set()
    for row in medicines:
        generic = row["generic"].strip()
        drugs.add((generic, "medicine"))
        if " / " in generic:
            for part in generic.split(" / "):
                drugs.add((part.strip(), "medicine"))
    for row in allergies:
        drugs.add((row["name"].strip(), "allergy"))

    brand_rows = sorted(brand_to_generic.values(), key=lambda pair: pair[0].lower())
    drug_rows = sorted(drugs, key=lambda pair: (pair[0].lower(), pair[1]))
    return medicines, allergies, brand_rows, drug_rows, problems


def check(medicines, allergies, brand_rows, drug_rows, problems):
    lookup = {brand.lower(): generic for brand, generic in brand_rows}
    known = {name.lower() for name, _ in drug_rows}

    def to_generic(shown):
        shown = shown.lower()
        return lookup.get(shown, shown if shown in known else None)

    # Everything Hospital C can write (brand, or the generic with a capital letter) must resolve.
    for row in medicines:
        shown = row["brand"] or row["generic"].capitalize()
        if to_generic(shown) != row["generic"]:
            problems.append(f"Hospital C medicine '{shown}' does not turn into '{row['generic']}'")
    for row in allergies:
        shown = row["brand"] or row["name"].capitalize()
        if to_generic(shown) != row["name"]:
            problems.append(f"Hospital C allergy '{shown}' does not turn into '{row['name']}'")

    # Rows already in the files (the four demo medicines from T05) must survive.
    for path, rows in ((BRAND_FILE, brand_rows), (DRUG_FILE, drug_rows)):
        if not path.exists():
            continue
        new = {tuple(cell.lower() for cell in row) for row in rows}
        for old in read_rows(path):
            if tuple(cell.lower() for cell in old.values()) not in new:
                problems.append(f"{path.name} would lose the row {list(old.values())}")
    return problems


def write(path, header, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="run the checks only, write nothing")
    args = parser.parse_args()

    medicines, allergies, brand_rows, drug_rows, problems = build()
    problems = check(medicines, allergies, brand_rows, drug_rows, problems)
    if problems:
        print("Problems found, nothing written:")
        for problem in problems:
            print("  -", problem)
        sys.exit(1)

    if not args.check:
        write(BRAND_FILE, ["brand", "generic"], brand_rows)
        write(DRUG_FILE, ["name", "kind"], drug_rows)
    print(f"OK: {len(brand_rows)} brand and other-name rows, {len(drug_rows)} drug list rows. "
          f"All {len(medicines)} medicine and {len(allergies)} allergy names Hospital C can write turn into a generic."
          + ("" if args.check else " Files written."))


if __name__ == "__main__":
    main()
