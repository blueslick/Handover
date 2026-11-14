# pipeline/data

**Python 3.11 or newer is needed.** pandas 3.0.5 does not install on Python 3.9 (the macOS system Python). Daniel uses Homebrew `python@3.12` in `.venv`.

## The Synthea download (not in git)

We use the Synthea **CSV sample, November 2021** (1,163 patients).

1. Download `synthea_sample_data_csv_nov2021.zip` from https://synthea.mitre.org/downloads
   (or from https://github.com/synthetichealth/synthea-sample-data, file `downloads/synthea_sample_data_csv_nov2021.zip`).
2. Unzip it so the CSV files sit in `pipeline/data/synthea_raw/csv/` (for example `pipeline/data/synthea_raw/csv/patients.csv`).

That folder is git-ignored, so it is never committed.

## The split (T11)

`select_patients.py` picks the patients and fixes the split. It reads only ages, sexes, whether a patient is alive, current-medicine counts and whether a drug allergy exists. It never reads record text, so nobody has to open a held-out patient.

```
python pipeline/data/select_patients.py pipeline/data/synthea_raw/csv pipeline/data
```

The seed is fixed (20261114), so rerunning it gives the same lists. To check, rerun it and confirm `git diff` shows no change.

| File | What it holds |
| --- | --- |
| `patients.csv` | patient_id, synthea_id, sex, age_band, split, drug_allergy |
| `split/working_ids.txt` | 20 working patients (P001-P020) |
| `split/heldout_ids.txt` | 80 held-out patients (P021-P100), 10 per age band x sex |
| `split/heldout_ext_ids.txt` | 80 reserve patients (R001-R080), same rule. Used only if we decide to expand before seeing any held-out result |

Age bands use age on 18 Nov 2021 (the last date in the sample): 0-19, 20-44, 45-64, 65+.
In each held-out group, up to 3 patients with a drug allergy are taken first, then the rest at random. The write-up must say this.
