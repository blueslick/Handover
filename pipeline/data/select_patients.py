"""Pick the patients and fix the split (T11).

Reads only patients.csv, medications.csv and allergies.csv from the Synthea
download, and looks only at age, sex, alive/dead, current-medicine counts and
whether a drug allergy exists. It never reads a patient's record text, so the
held-out set can be chosen without anyone opening it.

Usage:
    python select_patients.py <synthea_csv_folder> <output_folder>

Writes into <output_folder>:
    patients.csv               patient_id, synthea_id, sex, age_band, split, drug_allergy
    split/working_ids.txt      20 Synthea IDs
    split/heldout_ids.txt      80 Synthea IDs, 10 per age band x sex
    split/heldout_ext_ids.txt  80 more, same rule. Reserve only (see README note)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20261114
REF_DATE = pd.Timestamp("2021-11-18")  # last date in the Nov 2021 sample
BANDS = [(-1, 19, "0-19"), (19, 44, "20-44"), (44, 64, "45-64"), (64, 200, "65+")]
SEXES = ["F", "M"]
HELDOUT_PER_GROUP = 10
HELDOUT_ALLERGY_PER_GROUP = 3   # drug-allergy patients taken first in each group
WORKING_PER_GROUP = 2           # 2 x 8 groups = 16
WORKING_EXTRA_ALLERGY = 4       # 16 + 4 = 20


def age_band(age):
    for lo, hi, label in BANDS:
        if lo < age <= hi:
            return label
    raise ValueError(age)


def build_pool(src):
    p = pd.read_csv(src / "patients.csv")
    m = pd.read_csv(src / "medications.csv")
    a = pd.read_csv(src / "allergies.csv")

    p["age"] = ((REF_DATE - pd.to_datetime(p.BIRTHDATE)).dt.days / 365.25).astype(int)
    current = m[m.STOP.isna()]
    p["n_current_meds"] = p.Id.map(current.groupby("PATIENT").DESCRIPTION.nunique()).fillna(0)
    p["drug_allergy"] = p.Id.isin(a[a.CATEGORY == "medication"].PATIENT)

    pool = p[p.DEATHDATE.isna() & (p.n_current_meds >= 1)].copy()
    pool["age_band"] = pool.age.map(age_band)
    pool = pool.rename(columns={"Id": "synthea_id", "GENDER": "sex"})
    # Stable order before shuffling, so the seed alone decides the result.
    return pool.sort_values("synthea_id").reset_index(drop=True)


def take(df, n, rng):
    if n <= 0 or df.empty:
        return df.iloc[0:0]
    idx = rng.permutation(len(df))[:n]
    return df.iloc[idx]


def pick_group(group, n_total, n_allergy_first, rng):
    allergy = take(group[group.drug_allergy], n_allergy_first, rng)
    rest = group.drop(allergy.index)
    others = take(rest, n_total - len(allergy), rng)
    return pd.concat([allergy, others])


def main(src, out):
    rng = np.random.default_rng(SEED)
    pool = build_pool(src)
    groups = [(b, s) for _, _, b in BANDS for s in SEXES]

    def split_groups(available, per_group, allergy_first):
        picked = []
        for band, sex in groups:
            g = available[(available.age_band == band) & (available.sex == sex)]
            chosen = pick_group(g, per_group, allergy_first, rng)
            if len(chosen) < per_group:
                raise SystemExit(f"Not enough patients in {band} {sex}")
            picked.append(chosen)
        return pd.concat(picked)

    # 1. Held-out first, so it gets the scarce older drug-allergy patients.
    heldout = split_groups(pool, HELDOUT_PER_GROUP, HELDOUT_ALLERGY_PER_GROUP)
    remaining = pool.drop(heldout.index)

    # 2. Working: 2 per group, then 4 extra drug-allergy patients from anywhere.
    working = split_groups(remaining, WORKING_PER_GROUP, 0)
    remaining = remaining.drop(working.index)
    extra = take(remaining[remaining.drug_allergy], WORKING_EXTRA_ALLERGY, rng)
    working = pd.concat([working, extra])
    remaining = remaining.drop(extra.index)

    # 3. Reserve: a second held-out batch by the same rule. Only used if the
    #    decision to expand is made before any held-out result is seen.
    reserve = split_groups(remaining, HELDOUT_PER_GROUP, HELDOUT_ALLERGY_PER_GROUP)

    # Patient IDs: working P001-P020, held-out P021-P100, reserve R001-R080.
    # Order inside each set is shuffled so the ID says nothing about the group.
    rows = []
    for label, df, prefix, start in [("working", working, "P", 1),
                                     ("heldout", heldout, "P", 21),
                                     ("reserve", reserve, "R", 1)]:
        df = df.iloc[rng.permutation(len(df))]
        for i, (_, r) in enumerate(df.iterrows()):
            rows.append({"patient_id": f"{prefix}{start + i:03d}",
                         "synthea_id": r.synthea_id, "sex": r.sex,
                         "age_band": r.age_band, "split": label,
                         "drug_allergy": bool(r.drug_allergy)})
    table = pd.DataFrame(rows)

    (out / "split").mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "patients.csv", index=False)
    for label, fname in [("working", "working_ids.txt"), ("heldout", "heldout_ids.txt"),
                         ("reserve", "heldout_ext_ids.txt")]:
        ids = table[table.split == label].synthea_id
        (out / "split" / fname).write_text("\n".join(ids) + "\n", encoding="utf-8")

    # Summary: counts only, nothing from the records themselves.
    print(f"Pool: {len(pool)} alive patients with at least one current medicine")
    print(pd.crosstab([table.split, table.age_band], table.sex, margins=True))
    print("\nDrug allergies per set:")
    print(table.groupby("split").drug_allergy.sum())


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
