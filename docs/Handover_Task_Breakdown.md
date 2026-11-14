# Handover: task breakdown and owners

14 Nov 2026 · Daniel Tan · Companion to the Handover Pipeline and Frontend Plan

The plan breaks into about 50 tasks across five time blocks. Daniel builds the datasets tonight. On Sunday, Abby takes the test, Daniel the tool and Theo the Next.js app.

## Who takes which lane

| Who | Tonight | Sunday | Why |
| --- | --- | --- | --- |
| Daniel | Builds the datasets alone: record format, repo, patients, hospital records, answer keys, demo patient, sample file | Lane B core: extract, check, compile, store, and both full runs. Video editing | The API workspace, key and spend limit are set up. Claude Max can carry the most code |
| Abby | Out | Lane A from step 3 onward: checks the answer keys, writes the compile-rule tests and the scoring script, scores both runs. Also builds the keyword baseline, the omission check and the trap notes | Her evaluation experience matches scoring, breakdowns and failure analysis. The baseline and omission check are plain Python with no model, and they fill the hours when Lane A would wait |
| Theo | Out | Lane C: the Next.js app on Vercel, real data swap, screen recording, credits, submission. Labels the MTSamples notes by hand | Next.js to a live Vercel link is his strongest skill, and he has merged pull requests himself |

Four things to know about this split:

- **The load is roughly even, but not identical.** Daniel still carries the longest chain, because extraction, the working run and the held-out run cannot be split. Abby and Theo each have a full day of tasks that do not wait on him.
- **Daniel must not read the held-out records.** He builds the data tonight and tunes the prompt tomorrow. The scripts can generate held-out patients, but only Abby opens them, and she does the answer-key spot-check.
- **Abby asked for more building.** She pairs with Theo on the "How we tested" tab (T29, T39), which shows her own results.
- **Abby and Theo are on Claude Pro.** If either hits a usage limit on Sunday, the task moves to one of Daniel's sessions.

## Does the plan cover the backend

Yes. Lane B is the backend, and the plan does not need a separate backend document.

The backend here is not a server. It is a set of Python scripts (steps 4 to 9) that run on a laptop, call the Claude API once per hospital record, and write JSON files into the repo. The Next.js app then reads those files. There is no database and no live API route in the Must scope.

Moving to Next.js means the repo holds two languages: a `pipeline` folder in Python and an `app` folder in Next.js, deployed on Vercel. The JSON record format is the only thing they share. The API key stays in a git-ignored `.env` file for the pipeline. It goes into Vercel's environment variables only if live upload is switched on, which would also need the extraction prompt rewritten as a Next.js API route.

Three backend details are still open in the plan:

- Folder and file names for hospital records, model outputs, compiled records and results (Shared contracts, item 3).
- How the app loads the stored JSON: one file per patient, or one file for everyone.
- Whether live upload on the public app is switched on. The plan defers it, so the upload screen replays a saved extraction.

## Order and parallel work

Six steps must happen in order. Everything else can run side by side.

1. The record format (T01) comes before any code.
2. The working and held-out split (T11) is fixed before anything is run on a patient.
3. Hospital records (T13, T16) come before extraction and baselines. The answer key comes before scoring.
4. The model is picked on working patients (T21) before the full run (T31).
5. Model, prompt, brand table and compile rules are frozen (T35) before the held-out run (T36). The held-out run happens once.
6. Real results (T37) come before the results tab, the video and the write-up are final.

What runs in parallel:

- **All three people on Sunday morning.** Theo builds against the hand-written sample file, so the app never waits for real data.
- **Abby's work beside Lane B.** The compile-rule tests (T17), the scoring script (T18) and the keyword baseline (T24) need only the record format and the hospital records. None of them waits for extraction.
- **Two tracks for Daniel.** Extraction and checks (T19 to T22) and the compile rules (T23) do not depend on each other, so he can run them as two sessions.
- **Writing.** The write-up skeleton, credits list and video script can start before any results exist.

The branch rule: everyone pushes to `main`, and each person changes files only inside their own folder (`pipeline/data`, `pipeline/tool`, `pipeline/eval`, `app`). Say in the team chat before changing anything in `shared/`. Pull before every push and never force-push.

The longest chain is T01, T05, T13, T21, T31, T35, T36, T37, T39, T52. A delay on any of these delays the submission.

## Tonight (Saturday)

Daniel works alone tonight. The first nine rows are the minimum, in order. The last four are a stretch, and whatever is left goes to Sunday morning.

| ID | Task | Owner | Waits for | Level |
| --- | --- | --- | --- | --- |
| T01 | Set the record format and the fixed lists from the plan's draft. Abby and Theo confirm in the morning | Daniel | Nothing | Gate |
| T02 | Set the folders and file names from the plan, and write the branch rule into CLAUDE.md: everyone pushes to `main`, each person works only in their own folder | Daniel | T01 | Gate |
| T03 | Create the GitHub repo, add all three people, add the folder skeleton and a CLAUDE.md with the rules | Daniel | T02 | Must |
| T04 | Download the Synthea sample and open one patient's files | Daniel | Nothing | Must |
| T11 | Trim the patients and fix the split before anything runs: 20 working and 60 held-out, with 10 held-out patients per age and sex group. Commit the two ID lists | Daniel | T04 | Gate |
| T12 | Write the three hospital templates and set the CSV header: CSV table, free-text note, brand-name layout | Daniel | T11 | Must |
| T05 | Build the demo patient: three hospital records and its answer key, with a penicillin allergy only one hospital recorded, warfarin stopped, a metformin dose change and Panadol in the Hospital C record. Add all four to the drug list and the brand table | Daniel | T01, T12 | Must |
| T13 | Generate records for the first 5 working patients | Daniel | T11, T12 | Must |
| T06 | Hand-write the sample compiled record for the demo patient, so Theo can start at once | Daniel | T05 | Must |
| T14 | Stretch: write the answer key script | Daniel | T11 | Must |
| T16 | Stretch: generate records and answer keys for every patient, without opening the held-out ones | Daniel | T13, T14 | Must |
| T15 | Stretch: build the brand-to-generic table from the full brand list in the Hospital C template | Daniel | T12 | Must |
| T08 | Stretch: send one test record through the API and check the spend limit | Daniel | T13 | Must |

## Sunday morning

Start with a 15-minute call: Abby and Theo confirm the record format, and everyone fills the remaining TBDs (T10). Then the three build apart.

| ID | Task | Owner | Waits for | Level |
| --- | --- | --- | --- | --- |
| T10 | Confirm the record format, fill the TBDs in the tools table, run the interview command on the plan | Everyone | T01 | Must |
| T33 | Spot-check answer keys against Synthea's original records, including the held-out ones | Abby | T16 | Must |
| T17 | Write one test case for each of the six compile rules | Abby | T01 | Must |
| T18 | Write the scoring script against the sample file, with missed cases and false alarms counted separately | Abby | T06, T14 | Must |
| T24 | Build the keyword baseline with the stack-everything merge | Abby | T13 | Must |
| T19 | Write the extraction prompt so it returns JSON in the record format, on one record | Daniel | T08 | Must |
| T20 | Save every extraction and its token usage to a file, so later steps rerun without new calls | Daniel | T19 | Must |
| T21 | Run Sonnet 5.5 and Haiku 5.5 on 5 working patients, pick one, pin it, record tokens per call | Daniel | T13, T20 | Gate |
| T22 | Build the Check step, with one retry | Daniel | T19, T15 | Must |
| T23 | Implement compile rules 1 to 6 and pass Abby's test cases | Daniel | T01, T17 | Must |
| T25 | Define the JSON store layout, one fact per entry | Daniel | T02, T23 | Must |
| T09 | Scaffold the Next.js app, deploy it to Vercel and open the link on a phone without signing in | Theo | T03 | Must |
| T26 | Build the doctor screen against the sample file: banner, fact cards, critical facts first, conflicts side by side | Theo | T06, T09 | Must |
| T27 | Add the switch between Handover and Baseline | Theo | T26 | Must |
| T28 | Build the upload screen that replays a saved extraction and shows which step is running | Theo | T26 | Must |
| T29 | Build the "How we tested" tab with a placeholder table. Add the disclaimer to every tab, plus empty and failed states | Theo, with Abby | T26 | Must |
| T30 | Start the write-up skeleton and the credits list | Theo | Nothing | Must |

## Sunday afternoon

The lanes join. The freeze (T35) is the most important gate of the weekend: after it, nobody changes the prompt, the brand table or the rules.

| ID | Task | Owner | Waits for | Level |
| --- | --- | --- | --- | --- |
| T31 | Run the full tool on the 20 working patients and tune the prompt on those only | Daniel | T16, T21, T22, T23 | Must |
| T32 | Score the working patients and the baseline, and fix scoring bugs | Abby | T18, T24, T31 | Must |
| T34 | Swap the sample file for real compiled records and baseline records, then redeploy | Theo | T24, T25, T31 | Must |
| T41 | Build the omission check on the saved extractions | Abby | T20 | Should 2 |
| T40 | Type 20 trap notes and their twins. Daniel runs them, Abby scores them | Abby | T31 | Should 1 |
| T42 | Build the medSpaCy baseline, scored on extraction only | Abby | T24 | Should 3 |
| T43 | Label 12 MTSamples notes by hand. Daniel runs them, Abby scores them | Theo | T42 | Should 4 |
| T35 | Freeze the model, the prompt, the brand table and the compile rules | Everyone | T31, T32, T33 | Gate |
| T36 | Run every row of the build-up table on the held-out patients, once | Daniel | T35 | Gate |
| T37 | Score the held-out run: build-up table, missed cases and false alarms, age and sex breakdown | Abby | T36 | Must |
| T38 | Pick three failure examples and explain each | Abby | T37 | Must |

The omission check and medSpaCy are rows in the build-up table. If they are built, they must be finished on working patients before the freeze, not added afterwards.

## Sunday evening and Monday morning

| ID | Task | Owner | Waits for | Level |
| --- | --- | --- | --- | --- |
| T39 | Put the real results table and failure examples into the "How we tested" tab | Theo, with Abby | T37, T38 | Must |
| T45 | Walk through all the code as a team | Everyone | T36 | Must |
| T46a | Write-up: results, failure examples, limits | Abby | T37, T38 | Must |
| T46b | Write-up: framing and how the tool works | Daniel | Nothing | Must |
| T46c | Write-up: credits list with links, rules checklist | Theo | T30 | Must |
| T47 | Write the video script from the six shots | Abby | Nothing | Should 5 |
| T48 | Make the workflow diagram and title card | Daniel | Nothing | Should 5 |
| T49 | Screen-record shots 2 to 6 from the deployed app, showing real tool output and never the hand-written sample file | Theo | T34, T39 | Should 5 |
| T50 | Edit the two-minute video | Daniel | T47, T48, T49 | Should 5 |
| T51 | Final link check on a phone, signed out, with no API key needed | Everyone | T39 | Must |
| T52 | Submit: link and QR code, write-up, video, credits | Theo | T46, T51 | Gate |

## Things to settle

- [ ] **Recheck the spend limit.** The plan now expects about 600 to 700 calls for 80 patients. Measure tokens on the first patient and check the total against the limit.
- [ ] **Keep live upload off.** With a Python pipeline and a Next.js app, live extraction would mean writing the prompt twice. The upload screen replays a saved extraction.
- [ ] **Check file encoding across machines.** Theo is on Windows and the others are on Macs. Save every CSV and TXT as UTF-8, and test one file on Theo's machine in the morning.
