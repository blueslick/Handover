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
| `.superset/` | Paradev workspace setup and run scripts | Daniel |

- Change files only in the folders your person owns.
- If a task seems to need a change in someone else's folder, stop. Tell the person what change is needed and who owns the file. Do not make the change.
- Before changing anything in `shared/`, ask the person to confirm they have told the team.

## Git rules

- Everyone works on `main`. Do not create branches or pull requests unless the person asks. The one exception is the local branch a Paradev workspace starts on (see Parallel agents).
- Run `git pull --rebase` before every push.
- Never force-push. Never rewrite history. Never run `git reset --hard` on shared work.
- Commit small and often. Start each message with the task ID, for example `T23: add dose-change rule`.
- Stage only the files you changed for this task. Do not use `git add .` or `git add -A`.
- If a pull causes a conflict in a file you do not own, stop and tell the person.
- Daniel tags the freeze commit as `freeze`. Do not move or delete that tag.

### Who commits are credited to

- The author of every commit is the person whose computer made it (Daniel, Theo or Abby), using their own git name and email. Never set the author or committer to Claude, and never change anyone's git settings.
- Before the first commit of a session, run `git config user.name` and `git config user.email`. If either is empty or not the person's GitHub name and email, stop and ask them to fix it.
- End every commit message with Claude's `Co-Authored-By:` line. Claude Code adds it by default; never remove it. This is how the history shows that Claude helped, as the hackathon rules ask us to credit coding assistants.

## Parallel agents (Paradev workspaces)

Some sessions run in a Paradev workspace: its own git worktree, on its own local branch. You are in one if `git branch --show-current` prints anything other than `main`. Several of these can run at once. These rules add to the git rules above.

- One task ID per workspace. Do not take on a second task in the same workspace.
- Before changing anything, list the files this task will change and tell the person. Two workspaces running at once must not change the same file. Folder ownership already separates people; when one person runs several agents, split their work by file (for example `extract.py` in one, `compile.py` in another).
- Only one workspace at a time may change `shared/`, `pipeline/requirements.txt`, `.gitignore`, `CLAUDE.md` or `.superset/`. Ask the person to confirm no other workspace is changing that file.
- The workspace branch is a local scratch branch. Never push it and never open a pull request from it. Deliver each small, working commit straight to `main`:
  1. `git fetch origin`
  2. `git rebase origin/main`
  3. `git push origin HEAD:main`
  This replaces `git pull --rebase` for workspace sessions. If the push is rejected because `main` moved, repeat all three steps. Never force-push.
- Rebase onto `origin/main` at the start of the task and before every push, so each workspace stays close to `main`. Push as soon as a commit works; do not hold several unpushed commits.
- If a rebase stops on a conflict that is only in `docs/decisions.md`, keep both sides' lines in date order and continue. For any other conflict, run `git rebase --abort`, stop, and tell the person which files clashed.
- Only one workspace at a time runs the pipeline against the API. They share one key and one spend limit, and two runs on the same day could get the same run ID. Ask the person to confirm no other workspace is running one first.
- Each workspace runs its own dev server. If port 3000 is taken, Next.js uses the next free port; tell the person which one. Never stop a process you did not start.
- The setup script copies `.env` and links `pipeline/data/synthea_raw/` from the main checkout. Both are excluded from git locally; never commit them.
- Never remove or prune worktrees (`git worktree remove`, `git worktree prune`). The person deletes workspaces in Paradev.

## The shared record format

One fact looks the same everywhere: in the tool's output, the answer key, the baseline output and the app. The definition lives in `shared/`. Do not add, rename or remove a field in your own code. If the format needs to change, stop and tell the person.

The fixed lists are spelled one way only:

- Status: `current`, `stopped`, `none_recorded`, `suspected`, `family_history`, `planned`, `side_effect`
- Type: `allergy`, `medicine`, `diagnosis`, `operation`
- Flags: `unverified`, `conflict`, `missing_dose`, `possible_missed`, `dose_changed`, `unknown_name`

## Held-out patients

There are 20 working patients (P001-P020) and 160 held-out patients: P021-P100 plus the reserve R001-R080, which T59 added to the held-out set on 14 Nov, before any result was seen. That gives 20 held-out patients per age band x sex group. Reserve patients keep their R IDs and live in `pipeline/data/reserve/`; they count as held-out for every rule below and are scored with the held-out patients. The ID lists are in `pipeline/data/split/` and never change after they are committed.

- Tune, test and debug on working patients only.
- In a session run by Daniel, do not open, print, summarise or inspect any held-out record, answer key or output. Scripts may read and write those files, but their contents must not be shown. Daniel tunes the prompt, so he must not see them.
- Only Abby's sessions may open held-out files, and only for the answer-key spot-check and for scoring after the freeze.
- Do not run the tool on held-out patients before the `freeze` tag exists. The held-out run happens once (T36).
- Never change the split or the number of patients again (the T59 expansion was the one allowed change, made before any result).
- The demo patient is separate. It is not in either list and is never scored.

## After the freeze

Once the `freeze` tag exists, do not change the extraction prompt, the model, the brand-to-generic table, the drug list or the compile rules. If the person asks for such a change, remind them of the freeze and ask them to confirm with the team first.

## Model calls

- One model, pinned by its exact ID. Daniel picks the model in T21.
- Settings (T56): Claude 5.5 models refuse `temperature` (any value) and refuse thinking "disabled", so do not send `temperature`, `top_p` or `top_k`. Use the lowest thinking setting the model accepts (Sonnet 5.5: `between_tools`; Haiku 5.5: leave thinking out). Ask for a fixed JSON shape (`output_config`) that matches the record format. Results are repeatable because every reply is saved and later steps read the saved reply, never a new call. Extracted files record `temperature: null` and a `settings` line in words.
- Save every model response to `outputs/`, with the `usage` field (input and output tokens).
- Check, omission check, compile and scoring read saved outputs. They must not make new calls.
- Before any run of more than 10 calls, tell the person how many calls it will make and wait for a yes.
- One retry only, and only when an extraction fails the Check step. `pipeline/tool/run_records.py` runs many records and makes this retry; never write a second way of calling the model.
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
- Every fact card shows the fact, its status, the hospital and date, and any warning; its exact source quote is one tap away (never more than one tap, and never reworded).
- An unknown patient ID gets a clear message and the list of sample IDs.
- Keep the styling plain and readable, in the manner of clinical software. Do not copy any one real product's screens, name or logo.
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
