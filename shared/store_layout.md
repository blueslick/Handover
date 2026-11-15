# Store layout v1.0 (T25)

Set by Daniel, Sat 14 Nov 2026. Abby and Theo confirm at the Sunday call (T10).
This is pipeline section 8, "Store": compiled records kept as version-controlled JSON, one fact per entry.
It adds no new fact fields. Every fact is exactly the compiled fact in `shared/record_format.md`.

## What is the source of truth

The per-patient files are the store. Everything else is rebuilt from them by `pipeline/tool/store.py` and is never edited by hand.

| File | What it is | Source of truth? |
| --- | --- | --- |
| `<folder>/P014.json` | One patient's compiled record (compiled shape). Written by compile, a baseline, or the answer-key script | **Yes** |
| `<folder>/facts.jsonl` | The facts table: every fact from every patient in the folder, one fact per line | No, rebuilt by `store.py build` |
| `<folder>/index.json` | One line of counts per patient | No, rebuilt by `store.py build` |

`<folder>` is one of `outputs/compiled/<run_id>/`, `outputs/baseline_keyword/`, `outputs/baseline_medspacy/`.

## The facts table (`facts.jsonl`)

One JSON object per line, one line per fact. Each line is the compiled fact unchanged, with two fields added at the front so a line makes sense on its own:

```json
{"run_id": "20261115-v1-haiku-5-5", "kind": "compiled", "fact_id": "P014-F03", "patient_id": "P014", "type": "medicine", "name": "warfarin", "...": "every other compiled-fact field as in record_format.md"}
```

- Lines are sorted by `patient_id`, then in the order the facts appear in the patient's file.
- Every fact keeps its `hospital`, `date` and `sources`, so each entry is tagged with where and when it came from.
- A patient with no facts has no lines (they still appear in `index.json`).
- Use it for counting across patients (how many conflicts, how many unverified critical facts). Scoring still reads the per-patient files, so it matches on `type` + `name` per patient as `record_format.md` says.

## The index (`index.json`)

```json
{
  "format_version": "1.0",
  "kind": "compiled",
  "run_id": "20261115-v1-haiku-5-5",
  "patients": [
    {"patient_id": "P014", "file": "P014.json", "facts": 9, "critical_facts": 5,
     "critical_warnings": 1, "conflicts": 1}
  ]
}
```

- `critical_facts`: allergies and medicines (the danger tiers in the plan).
- `critical_warnings`: critical facts flagged `unverified`, `conflict` or `missing_dose`. These are the ones that raise the app's warning banner.
- `conflicts`: number of different `conflict_group`s.

## Checks before anything is written

`store.py build` stops and writes nothing if any of these fail:

1. Every per-patient file passes `shared/validate.py`.
2. The file name matches its `patient_id` (`P014.json` holds `P014`).
3. Every file in the folder has the same `kind` and `run_id`.

It prints counts only, never facts, so it is safe to run on held-out output.

## What the app gets (`outputs/published/`)

Only Daniel writes here (CLAUDE.md). `store.py publish` fills it from one run:

```
outputs/published/
├── index.json                 which patients the app may show, and their counts
├── compiled/P014.json         copied from outputs/compiled/<run_id>/
├── baseline_keyword/P014.json copied from outputs/baseline_keyword/, if that patient has one
├── results/                   copied from outputs/results/<run_id>/ when --results is given
├── omission/P014.json         omission-check flags for the same run, when --with-omission is given (T64)
└── extraction_walkthrough/    left alone by store.py (filled later, for the upload replay)
```

`published/index.json`:

```json
{
  "format_version": "1.0",
  "compiled_run_id": "20261115-v1-haiku-5-5",
  "patients": [
    {"patient_id": "D001", "has_baseline": true, "facts": 7, "critical_facts": 5,
     "critical_warnings": 2, "conflicts": 1}
  ]
}
```

- Publishing replaces everything in `published/compiled/` and `published/baseline_keyword/`, so no patient from an older run is left behind.
- Only the frozen run (git tag `freeze`) plus the demo patient go here for the submission (folders_and_names.md). Write the run ID in the Log tab.

## Omission flags for the app (T64, added 15 Nov)

`store.py publish --with-omission` joins the omission check's per-record files
(`outputs/omission/<run_id>/<PID>_<H>.json`, Abby's `omission_check.py`) into one file per patient,
`published/omission/<PID>.json`. The omission run must be the same run ID as the compiled run. Nothing in the omission check changes; this only copies its saved output.

```json
{
  "format_version": "1.0",
  "kind": "omission_check",
  "patient_id": "D001",
  "run_id": "20261115-v2-demo-sonnet-5-5",
  "records": [
    {"hospital": "A", "source_file": "D001_A.csv",
     "flags": [{"flag": "possible_missed", "generic": "warfarin", "terms_as_written": ["Coumadin"],
                "lines": [{"line": 3, "text": "Coumadin 5 mg"}]}]}
  ],
  "not_checked": ["B"]
}
```

- `flags` are exactly the omission check's flags. `not_checked` lists hospitals with no omission file (no saved extraction).
- The index entry gains `"omission_flags"`: the number of flags, or `null` if no record was checked. Without `--with-omission` the field is left out and nothing goes in `published/omission/`.
- The app copies it to `app/data/<ID>_omission.json` (sync-data.mjs) and shows it in its own "Possibly missed: word-search hint" box under the record, never as a fact and never in the warning banner.
- These files are not fact records, so `shared/validate.py` does not check them; `store.py` checks kind, patient ID and run ID instead.

## For Theo's sync script

`app/data/` is still filled by Theo's sync script from `outputs/published/`. Today the app reads `app/data/D001_compiled.json` and keeps a hand-written `SAMPLE_IDS` list. With this layout the sync can copy `published/compiled/P014.json` to `app/data/P014_compiled.json` (or the app can switch to the folder names; Theo's call), and the app can take its list of allowed IDs from `index.json` instead of typing them in.

## Commands

```
python pipeline/tool/store.py build outputs/compiled/<run_id>
python pipeline/tool/store.py build outputs/baseline_keyword
python pipeline/tool/store.py publish --run <run_id> [--patients D001 P021 ...] [--results <run_id>]
```
