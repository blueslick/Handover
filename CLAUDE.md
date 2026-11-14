# CLAUDE.md: rules for this repo

Read this file before doing anything. It applies to every Claude Code session, whoever is running it.

## What this project is

Handover is a hackathon prototype (Veritas AI, Health track). It merges one patient's records from three hospitals into one record, where every fact shows its source. Then it measures how often it gets an allergy or a medicine wrong, against a simple baseline.

- The pipeline is Python. It runs on a laptop, calls the Claude API once per hospital record, and writes JSON files.
- The app is Next.js on Vercel. It only reads those JSON files. It never calls the model.
- All data is synthetic (Synthea) or public. No real patient records, ever.
- Deadline: submit on Monday morning, 16 Nov 2026.

The full plan is `docs/Handover_Pipeline_and_Frontend_Plan.md`. The task list is `docs/Handover_Task_Breakdown.md`. Task IDs such as T19 refer to that list and to the command centre sheet. If this file and the plan disagree, stop and ask.

## First step in every session

Ask the person who they are (Abby, Daniel or Theo) and which task ID they are working on, unless they have already said. Their name decides which folders you may change.

## Who owns which folder

| Folder | Holds | Who may change it |
| --- | --- | --- |
| `shared/` | Record format, fixed lists, sample file, drug list, brand-to-generic table | One person at a time, after telling the team |
| `pipeline/data/` | Patients, hospital records, answer keys, ID lists | Daniel on Saturday night, then Abby |
| `pipeline/tool/` | Extract, check, compile, store | Daniel |
| `pipeline/eval/` | Compile-rule tests, scoring, baselines, omission check | Abby |
| `outputs/` | Saved model outputs, compiled records, baseline records, results | Whoever ran the script that writes the file |
| `app/` | The Next.js app | Theo |
| `docs/` | Plan, task breakdown, write-up, credits | Anyone |

- Change files only in the folders your person owns.
- If a task seems to need a change in someone else's folder, stop. Tell the person what change is needed and who owns the file. Do not make the change.
- Before changing anything in `shared/`, ask the person to confirm they have told the team.

## Git rules

- Everyone works on `main`. Do not create branches or pull requests unless the person asks.
- Run `git pull --rebase` before every push.
- Never force-push. Never rewrite history. Never run `git reset --hard` on shared work.
- Commit small and often. Start each message with the task ID, for example `T23: add dose-change rule`.
- Stage only the files you changed for this task. Do not use `git add .` or `git add -A`.
- If a pull causes a conflict in a file you do not own, stop and tell the person.
- Daniel tags the freeze commit as `freeze`. Do not move or delete that tag.

## The shared record format

One fact looks the same everywhere: in the tool's output, the answer key, the baseline output and the app. The definition lives in `shared/`. Do not add, rename or remove a field in your own code. If the format needs to change, stop and tell the person.

The fixed lists are spelled one way only:

- Status: `current`, `stopped`, `none_recorded`, `suspected`, `family_history`, `planned`, `side_effect`
- Type: `allergy`, `medicine`, `diagnosis`, `operation`
- Flags: `unverified`, `conflict`, `missing_dose`, `possible_missed`, `dose_changed`, `unknown_name`

## Held-out patients

There are 20 working patients and 60 held-out patients. The ID lists are in `pipeline/data/` and never change after they are committed.

- Tune, test and debug on working patients only.
- In a session run by Daniel, do not open, print, summarise or inspect any held-out record, answer key or output. Scripts may read and write those files, but their contents must not be shown. Daniel tunes the prompt, so he must not see them.
- Only Abby's sessions may open held-out files, and only for the answer-key spot-check and for scoring after the freeze.
- Do not run the tool on held-out patients before the `freeze` tag exists. The held-out run happens once (T36).
- Never change the split or the number of patients.
- The demo patient is separate. It is not in either list and is never scored.

## After the freeze

Once the `freeze` tag exists, do not change the extraction prompt, the model, the brand-to-generic table, the drug list or the compile rules. If the person asks for such a change, remind them of the freeze and ask them to confirm with the team first.

## Model calls

- One model, pinned by its exact ID, temperature 0, no extended thinking, JSON output that matches the record format. Daniel picks the model in T21.
- Save every model response to `outputs/`, with the `usage` field (input and output tokens).
- Check, omission check, compile and scoring read saved outputs. They must not make new calls.
- Before any run of more than 10 calls, tell the person how many calls it will make and wait for a yes.
- One retry only, and only when an extraction fails the Check step.
- The model never labels data or grades its own output. People write answer keys and labels.

## Secrets

- The API key lives in a git-ignored `.env` file. Never print it, commit it or put it in `app/`.
- Check that `.env` is in `.gitignore` before the first commit.
- The app must work with no API key at all.

## Honest results

- Never edit a saved output, a score or a results table by hand. If a result looks wrong, fix the code and rerun it.
- Never invent a number. If something was not run, say so.
- Do not hide weak results. The write-up reports real numbers, including failures.
- The hand-written sample file is only for building the app. It must not appear in the results, the video or the final app.
- Report missed cases and false alarms separately.

## Python rules (`pipeline/`)

- Read and write every file as UTF-8, and say so in the code: `open(path, encoding="utf-8")`. Theo is on Windows and the others are on Macs.
- Build paths with `pathlib`. Do not write paths with backslashes or absolute paths.
- Hospital records are written by code templates, not by a model.
- Set a seed for anything random, and record it.
- Add a new package to `requirements.txt` with its version.
- Give long scripts a small test mode that runs on one or two working patients first.

## App rules (`app/`)

- The app reads JSON from the repo. It makes no model calls and needs no key.
- Every tab shows this line at the bottom: "This project is a prototype and is not medical advice."
- Allergies and current medicines appear first, before any scrolling.
- When two hospitals disagree, show both. Never hide one or pick a winner.
- Show every status as a word, never by colour alone.
- Every fact card shows the fact, its status, the hospital and date, the source quote, and any warning.
- An unknown patient ID gets a clear message and the list of sample IDs.
- Keep the styling simple. Do not copy the look of a real clinical system.
- A push to `main` goes live on Vercel. Run the build locally before pushing.

## How to explain your work

All three people direct the code through Claude Code and check it by reading. None of them writes code from scratch.

- Put a short plain-language comment above each block of code, saying what it does and why.
- When you finish a task, say in plain language what changed, which files, and how the person can check it works.
- Add one dated line to `docs/decisions.md` for each fix or decision you made.
- If something is unclear, ask one question before building. Do not guess.
- Do one task at a time. Do not start a "Should" task while a "Must" task for the same person is unfinished.
- Do not say a task is done unless you ran it and saw it work.

## Team rules

Rules that the rest of this file does not already cover. Branches, folder owners, held-out data, freeze and API keys are all set out above.

### Formats

- Every JSON fact follows `shared/record_format.md`. Run `python shared/validate.py <file>` before committing outputs, answer keys or the sample.
- Folder and file names follow `shared/folders_and_names.md`.
- Every app tab and the write-up carry this line: "This project is a prototype and is not medical advice."

### Shared folder

- When you finish a change to `shared/`, tell the team chat that it is done, so the next person knows they can write there.

### Folder hand-offs

- `pipeline/data/` belongs to Daniel until Daniel posts in the team chat that the data is handed over (target Saturday night; unfinished stretch tasks may run into Sunday morning). After that it belongs to Abby.
- In `outputs/`, whoever ran the script that writes a file owns it. `outputs/published/` has one writer, Daniel, because it holds the frozen run the app shows.
