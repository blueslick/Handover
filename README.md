# Handover

When a patient arrives at an emergency department, their history is often split across several hospitals, each
writing records in its own way. Handover reads the records from three hospitals and merges them into **one record
for the doctor**, with the hospital, date and a word-for-word quote behind every fact. Where the hospitals
disagree (for example, one lists a penicillin allergy and another says "no known allergies"), Handover shows both
side by side instead of picking one.

This is a hackathon prototype built on synthetic patients only. It is not medical advice.

- **App:** https://veritas-ai-hackathon.vercel.app (no sign-in, no API key needed)
- **Write-up:** https://docs.google.com/document/d/1lHzcvi0vvmdCBLFHJB3e1dCduw-LKhDw7dX_G8oRlHE/edit

## How it works: three steps

1. **Extract (Claude, AI).** Claude Sonnet 5.5 reads each hospital record and lists every allergy, medicine,
   diagnosis and operation, each with a status label (for example current or stopped) and an exact quote.
2. **Check (code, no AI).** Each quote must appear word for word in the record and each name must be on the drug
   list; brand names are turned into generic names. A record with problems gets one retry, and a fact that still
   fails is kept and marked unverified, never dropped.
3. **Merge (code, no AI).** Six fixed rules join the three lists into one record: one fact per drug, a later stop
   or dose change wins (the older value is kept in the history), a hospital that doesn't mention a drug is not
   treated as a stop, and "no known allergies" against a recorded allergy, or any other disagreement on an
   allergy or medicine, is kept on every side as a conflict.

## How it was tested

- 180 synthetic patients from Synthea, each with three hospital records in three different layouts (a table, a
  free-text letter, and a sheet that uses brand names). The correct answer for each patient is built by code
  from the patient's history, not by the AI.
- The prompt was tuned on 20 working patients only. The tool was then frozen and run once on **160 held-out
  patients**, 20 in each of four age bands for each sex.
- Results on the held-out patients (all 1,668 facts in the answer keys): the full tool missed **13** facts, raised
  **47** false alarms and showed **38 of 38** conflicts. A keyword-search baseline missed 916 facts, raised 1,312
  false alarms and showed none of the conflicts.
- The full table, step by step from the baseline to the full tool, is on the app's "How we tested" tab. It is
  built from the files in `outputs/results/heldout/`.

## Folder guide

| Folder | What is in it |
|---|---|
| `app/` | The website (Next.js). It only reads saved results; it never calls a model. |
| `pipeline/data/` | Synthetic patients, hospital records, answer keys and the scripts that make them |
| `pipeline/tool/` | The tool itself: extract, check, merge (compile) and the saved-call layer |
| `pipeline/eval/` | Scoring, the baselines and the omission check |
| `outputs/` | Saved model replies, merged records, baseline records and results |
| `shared/` | The record format, folder and file names, drug list and brand-name table |
| `docs/` | Plan, decisions log, failure examples |

## Run the app on your own computer

You need Node.js 20 or newer.

```
cd app
npm install
npm run dev
```

Then open http://localhost:3000. No API key is needed: the app shows saved results only.

To rebuild the results file for the "How we tested" tab from the committed held-out totals, run
`node scripts/make-results.mjs` from `app/`.

The pipeline (Python 3.11 or newer) needs the Synthea download described in `pipeline/data/README.md`, and an
Anthropic API key to make new model calls.
