> **Update, 14 Nov night (T11):** the dataset is now 100 scored patients: 20 working (P001-P020) and 80 held-out (P021-P100), 10 per group across four age bands (0-19, 20-44, 45-64, 65+) and two sexes, plus an 80-patient reserve (R001-R080). Where this plan says 80 patients, 60 held-out or three age bands, `docs/decisions.md` and `shared/` win. Expected calls rise to about 300 per prompt version.

# Handover: Pipeline and Frontend Plan

Nov 14, 2026 · @Abby Tan · Revised 14 Nov after team review · Updated 14 Nov evening (Next.js, dataset size, owners)

## How this doc works

The project splits into three lanes that meet at one shared record format, so three people can build in parallel on Sunday. This doc sits on top of Dan's plan v2 and does not replace it. Where the two disagree, the "Changes since plan v2" section below wins.

- **Lane A, the test:** data, answer key, scoring, results.
- **Lane B, the tool:** extraction, checks, compile rules, storage, baselines.
- **Lane C, the face:** the app, the demo video, the write-up, the submission.

Tonight: Daniel builds the datasets alone (see "Tonight's checklist"). All ten gaps have a decision. The full task list, with owners and order, is in [Handover: task breakdown and owners](https://claude.ai/artifact/Vs6AQkKXZmVQ7vSMwv8e5t).

## Changes since plan v2

These were agreed on 14 November.

| Area | Change |
| --- | --- |
| Model | Claude API, paid by the team. One model version, pinned, temperature 0, JSON output. Sonnet 5.5 by default; Haiku 5.5 if it does as well on the working patients (see "Model and cost") |
| New step | Omission check after the Check step. It flags facts that appear in a source record but are missing from the output |
| medSpaCy | Moved from If time to Should. It gets its own row in the build-up table, scored on extraction only |
| Age and sex breakdown | Moved from Should to Must. The Health track says judges check this |
| Brand-to-generic table | A Must, built from the template's full brand list, frozen before the held-out run |
| Compile rules | Written out in full below, including a rule for dose changes |
| MIMIC-IV | Dropped. It contains real patients' records, and the brief says not to use real patient records |
| Patient download | Out of scope. Moved to future directions with identity checks |
| Uploads | Hospital staff upload records, not patients |
| Framing | Open with Malaysia's records rollout as the hook, then move straight to the emergency doctor (see "Framing") |
| Cut order | Identity matching, repair loop, MTSamples, medSpaCy, video. Never cut the baseline, the held-out split, the failure examples or the age and sex breakdown |

## Changes on 14 November evening

These came after the team review. Where they disagree with anything older, they win.

| Area | Change |
| --- | --- |
| Framework | Next.js on Vercel, not Gradio on Hugging Face Spaces. The pipeline stays in Python and writes JSON. The app only reads that JSON |
| Repo | Two languages in one repo: `pipeline` (Python) and `app` (Next.js), plus `shared` and `outputs` folders. The record format is the only thing the two languages share |
| Dataset size | 80 patients, not 40: 20 working and 60 held-out. The held-out set has 10 patients in each of six groups (three age bands, two sexes), so the age and sex breakdown rests on more than a few people per group |
| Owners | Abby takes Lane A, Daniel takes Lane B, Theo takes Lane C |
| Datasets | Daniel builds sections 1 to 3 on Saturday night. He also tunes the prompt, so he does not open held-out records. Abby does the answer-key spot-check |
| Sections 6 and 9 | Abby builds the omission check and the baselines. They need no model, and they fill the hours when Lane A would wait for Lane B |
| Live upload | Stays off. It would need the extraction prompt written a second time as a Next.js API route |
| Calls | About 600 to 700, up from 300 to 400 |
| Model comparison | Sunday morning, not Saturday night. It needs the first 5 working patients and the saved-output code, so it is task T21 |
| Branch rule | Everyone pushes to `main`, and each person works only inside their own folder. Shared files change only after a message to the team (see "Shared contracts") |
| Demo patient | Uses familiar medicines: a penicillin allergy that only one hospital recorded, warfarin (shown as "a blood thinner") stopped, a metformin dose change, and Panadol for paracetamol in the Hospital C record. The input is staged and the output is not (see "Demo video first") |

## Framing

The user is an emergency doctor. The national rollout is the hook, not the user.

> "In an emergency you're taken to the nearest hospital, not your usual one, and they don't have your records. Countries like Malaysia are building shared record systems to fix this. But those systems have to merge records from hospitals that each write things differently. We built that merging step, where every fact shows its source, and then tested how often it gets an allergy or a medicine dangerously wrong."

- Why the emergency doctor: the patient is new to the hospital, may not be able to speak, and the first decision is often a prescription within minutes.
- Do not claim the tool plugs into any national system. Say "our output follows the FHIR layout".
- A GP or pharmacist could also benefit. Mention that once, but keep the story on the emergency doctor.

## Demo video first

The two-minute video decides what the app must show, so the screens are designed backwards from the shots. Shot lengths follow plan v2.

| Shot | Time | What the viewer sees | What the app needs |
| --- | --- | --- | --- |
| 1. The problem | 0:00 to 0:15 | A doctor, a patient with records at three hospitals, one sentence on the risk | Nothing. A title card or slide |
| 2. Upload | 0:15 to 0:35 | Three records in three formats go in. Extracted facts appear with labels and quotes | Upload screen, with a loading state that looks good on camera. Plays back saved outputs |
| 3. Baseline gets it wrong | 0:35 to 0:50 | The baseline record lists a stopped blood thinner as current | A "Baseline" view of the same patient |
| 4. Our record | 0:50 to 1:15 | Warfarin shown as stopped, with hospital, date and quote. A conflict warning on an allergy | Doctor screen: banner, critical facts first, conflict shown side by side |
| 5. How it works | 1:15 to 1:45 | Workflow diagram, the data, the build-up table | A "How we tested" tab with the real results table |
| 6. Next steps | 1:45 to 2:00 | One failure example and what comes next | The failure shown in the app, or a slide |

Four things follow from this:

- **One demo patient carries the whole video.** They need a stopped blood thinner, an allergy only one hospital recorded, and a dose change. Lane A plants this patient; Lane C preloads them. The demo patient is not one of the held-out patients, so it never affects the results.
- **The demo patient uses medicines viewers know.** The allergy is penicillin. The stopped blood thinner is warfarin, called "a blood thinner" on screen and in the voiceover. The dose change is metformin, called "a diabetes medicine". The Hospital C record writes Panadol for paracetamol, to show the brand-to-generic step. All four go into the drug list and the brand-to-generic table. The 80 scored patients keep whatever Synthea gives them.
- **Staged input, real output.** We choose the demo patient and write their three records. What the app shows is what the tool and the baseline really produced on those records. If the tool gets the demo patient wrong, change the patient or fix the tool, and never edit the saved output. Record the video only after the hand-written sample file has been replaced by real output. Say in the video or the write-up that this is a patient we built to show three cases. Describe the risk as "the doctor would be working from a wrong medicine list", and do not claim a specific clinical harm.
- **The baseline needs its own view.** Shot 3 only works if the app can show the baseline's record beside ours.
- **Saved results, not live calls, on camera.** The demo patient's output is stored so the recording and the public link never wait on the model, hit a limit or spend API credit.

## Frontend

The app is one page with three tabs, built in Next.js, so every video shot is a screen that already exists.

### UI: what is on each screen

| Screen | For | Contains |
| --- | --- | --- |
| Doctor lookup | The emergency doctor | Patient ID box. Warning banner. Allergies, then medicines, then diagnoses and operations. A switch between "Handover" and "Baseline" |
| Hospital upload | Hospital staff | Hospital picker (A, B, C). File upload or paste box. The extracted facts for that record |
| How we tested | Judges | The build-up table, the breakdowns, three failure examples |

Every fact on the doctor screen is one card with the same five parts:

1. The fact itself, such as "Warfarin 3 mg daily".
2. A status label in words, such as "Stopped".
3. The hospital and date it came from, plus earlier values if it changed.
4. The source quote, shown under the fact.
5. A warning, if it is unverified, in conflict, missing a dose, possibly missed, changed dose or an unknown name.

The line "This project is a prototype and is not medical advice." sits at the bottom of every tab.

### UX: how it behaves

- **Critical first.** Allergies and current medicines appear before any scrolling.
- **Conflicts side by side.** Two hospitals that disagree are both shown. The app never hides one.
- **Labels in words.** A status is never shown by colour alone.
- **Nothing to learn.** The doctor types an ID and reads. Sample IDs are listed under the box.
- **Loading.** Extraction takes several seconds, so the upload screen shows which step is running.
- **When the model fails.** The app says so and offers the preloaded patients instead of a blank page.
- **Empty states.** An unknown patient ID gets a clear message and the sample IDs.
- **Keep the styling plain and readable, in the manner of clinical software.** Do not copy any one real product's screens, name or logo.

### Tools

| Job | Tool | Status |
| --- | --- | --- |
| Building the screens | Claude Code | Agreed |
| App framework | Next.js | Agreed (Gap 1, changed 14 Nov evening) |
| Hosting and the QR link | Vercel | Agreed. Check the link opens on a phone without signing in |
| Sketching screens before building | Paper, or Claude's Design artifacts | TBD |
| Checking the live page | Claude's browser tools | TBD |
| Screen recording and editing | QuickTime and CapCut | TBD |
| Workflow diagram and title card | Canva | TBD |
| MCPs and connectors | GitHub via the gh command line, Google Drive for the command-centre sheet | TBD: add any others |

## Pipeline map

Eleven sections run from raw patients to the submission, and each one hands a named file to the next. The app sits near the end of the build order, but it can be built first against a sample file (see Shared contracts).

| # | Section | Goes in | Comes out | Lane | Tools |
| --- | --- | --- | --- | --- | --- |
| 1 | Patients | Synthea sample download | 80 trimmed patients, split 20 working and 60 held-out | A (Daniel, Saturday night) | Synthea, Python, pandas |
| 2 | Hospital formats | One patient's history | Three records per patient: CSV table, free-text note (TXT), brand-name layout (TXT) | A | Python templates, no AI |
| 3 | Answer key | Synthea's original record, plus any planted traps | The correct compiled record per patient | A (Daniel, Saturday night) | Python script, 5 checked by hand by Abby |
| 4 | Extract | One hospital record | Facts with status labels and quotes, as JSON | B | Claude API (one pinned model, temperature 0), Python |
| 5 | Check | Extracted facts and the source record | Facts marked verified or flagged, one retry | B | Python, drug list and brand-to-generic table |
| 6 | Omission check | Extracted facts and the source record | "Possible missed fact" flags for drug names and allergy words found in the source but missing from the output | B (built by Abby) | Python, the same drug list |
| 7 | Compile | All facts for one patient | One merged record with history and conflicts marked | B | Python, the compile rules below |
| 8 | Store | Compiled records | Version-controlled JSON files, one fact per entry | B | JSON in the repo |
| 9 | Baselines | The same hospital records | Keyword record with a stack-everything merge (Must). medSpaCy record (Should) | B (built by Abby) | Python word lists, medSpaCy |
| 10 | Score | Tool output, baseline outputs, answer key | The build-up table and breakdowns | A | Python, Colab notebook |
| 11 | Show and tell | The stored records and the results | The app, the video, the write-up, the submission | C | Next.js. See Frontend tools |

Extra data sets enter at section 4 and are scored at section 10. Both belong to Lane A:

- **20 typed trap notes** (Should, first). Short notes we type, each hiding one trap, plus a twin where the fact is true.
- **12 MTSamples notes** (Should, after medSpaCy is working). Typed sample notes in real doctors' style, from a public Kaggle dataset. They test extraction on writing we did not produce. People label them by hand, not Claude, so the model never grades its own work.

### Compile rules

These are the rules Lane B implements and Lane A writes test cases for.

1. **Same drug, one fact.** Brand names are converted to generic first. The same drug at several hospitals becomes one fact that lists every source.
2. **Explicit stop.** A later record that says a drug was stopped or discontinued sets it to "Stopped". The earlier "Current" entry stays visible in the history.
3. **Dose change.** A later dated dose for the same drug replaces the earlier dose. The earlier dose stays visible in the history, and the card shows "dose changed". Keeping the old dose, or listing both as current, is an error.
4. **Silence is not a stop.** A later record that simply does not mention a drug does not remove it or stop it. The fact stays, showing the hospital and date it was last recorded.
5. **Allergies are never removed automatically.** If one hospital says "no known allergies" and another records an allergy, both are shown side by side with a conflict warning.
6. **Anything else on a critical fact is a conflict.** If two hospitals disagree on an allergy or a current medicine and rules 2 to 4 do not settle it, both are shown with a conflict warning. The app never silently picks a winner on a critical fact.

## Model and cost

- **Choosing the model.** Run Sonnet 5.5 (`claude-sonnet-5-5`) and Haiku 5.5 (`claude-haiku-5-5`) on the first 5 working patients on Sunday morning. If Haiku makes no more critical errors, use Haiku. Choose using working patients only, never held-out results.
- **Freezing it.** One model version and temperature 0 for every row of the build-up table and for the final run. No extended thinking. Ask for JSON that matches the shared record format.
- **Saving outputs.** Every extraction is saved to a file, along with the `usage` field from the API response (input and output tokens). Checks, the omission check, compiling and scoring rerun from saved files without new calls.
- **Expected calls.** 80 patients times 3 records is 240 calls for each prompt version. Plain lists and status labels are two versions, so 480. With trap notes, MTSamples, tuning and retries, expect about 600 to 700 calls.
- **Expected cost.** About 1,500 tokens in and 600 out per call. Measure the real figure from the first patient's `usage` fields and multiply out. Check prices on the official pricing page before setting the cap.
- **Spending cap.** Set a monthly spend limit in the Claude Console (Organization settings, then Billing, then Spend limits), with a notification below it. Track spend on the Usage and Cost pages. The USD 20 to 30 limit was set for 300 to 400 calls, so recheck it against the measured cost of 700.
- **The key.** The pipeline reads it from a git-ignored `.env` file on the machine that runs extraction. It goes into Vercel's environment variables only if live upload is ever switched on. Never in the repo or the frontend code.

## The three lanes

Each lane owns three to six sections and can start on Sunday morning without waiting for the others. Plan v2 gave the build lead nearly all the code; this split spreads it.

|  | Lane A: the test | Lane B: the tool | Lane C: the face |
| --- | --- | --- | --- |
| Person | Abby (Daniel builds sections 1 to 3 on Saturday night) | Daniel | Theo |
| Sections | 1 Patients, 2 Hospital formats, 3 Answer key, 10 Score | 4 Extract, 5 Check, 7 Compile, 8 Store (Daniel). 6 Omission check, 9 Baselines (Abby) | 11 App, video, write-up, submission |
| Also owns | Typed trap notes, MTSamples notes, the demo patient, compile-rule test cases, the age and sex breakdown | The model's instructions, the saved model outputs, the API key and cost tracking | Credits list, rules checklist, the QR link |
| Hands over | Hospital records to B. Results table to C | Compiled records to A for scoring and to C for display | Screen needs back to A and B |
| Suits someone who | Is careful with detail and knows the health content | Is most comfortable with Python and the model API | Cares about design and explains things clearly |
| First task Sunday | Spot-check the answer keys, then write the compile-rule test cases | Get one record through section 4 | Build the doctor screen against the sample file |
| Done when | The build-up table is filled from the 60 held-out patients | The full tool runs on the 20 working patients | A stranger can open the link and read the demo patient's record |

### Where the lanes meet

- **A to B:** hospital records, in an agreed folder and file naming.
- **B to A:** one compiled record per patient, in the shared record format.
- **B to C:** the same compiled records, which the app displays.
- **A to C:** the results table and three failure examples.
- **C to A and B:** what the video needs, mainly the demo patient and the baseline view.
- **A and B together:** the brand-to-generic table.

### Shared jobs

- The team walk-through of all the code on Sunday evening.
- The final link check on Monday morning.
- Spot-checking 5 answer keys: done by Abby, because Daniel built them. Daniel does not open held-out records.

## Shared contracts

Four agreements let the lanes build separately and still fit together on Sunday afternoon. Daniel sets them on Saturday night and the team confirms them on Sunday morning.

1. **The record format.** One fact looks the same everywhere: in the tool's output, the answer key and the app. A first draft, to edit tonight:

```json
{
  "patient_id": "P014",
  "type": "medicine",
  "name": "warfarin",
  "dose": "3 mg",
  "frequency": "daily",
  "status": "stopped",
  "hospital": "C",
  "date": "2026-03-02",
  "quote": "warfarin stopped two months ago",
  "history": [
    {"status": "current", "dose": "3 mg", "hospital": "A", "date": "2024-05-10"}
  ],
  "flags": ["conflict"]
}
```

2. **A sample file.** One hand-written compiled record for the demo patient, in that format. Lane C builds the app against it from the first hour, and Lane B aims its output at it.
3. **Folders and file names.** Where hospital records, model outputs, compiled records and results live in the repo. The layout is:
   - `shared/`: the record format, the fixed lists, the sample file, the drug list and the brand-to-generic table.
   - `pipeline/data/`: patients, hospital records and answer keys (Daniel on Saturday night, then Abby).
   - `pipeline/tool/`: extract, check, compile and store (Daniel).
   - `pipeline/eval/`: compile-rule tests, scoring, baselines and the omission check (Abby).
   - `outputs/`: saved model outputs, compiled records, baseline records and results.
   - `app/`: the Next.js app (Theo). Vercel builds from this folder only.
4. **The fixed lists**, spelled one way:
   - Status labels: current, stopped, none_recorded, suspected, family_history, planned, side_effect.
   - Record types: allergy, medicine, diagnosis, operation.
   - Flags: unverified, conflict, missing_dose, possible_missed, dose_changed, unknown_name.

Daniel creates the one GitHub repo on Saturday night. The branch rule:

- Everyone pushes to `main`. There are no long-lived branches and no pull requests on Sunday.
- Each person changes files only inside their own folder. That is what keeps three people on `main` from colliding.
- `shared/` and `outputs/` have one writer at a time. Say in the team chat before changing anything in `shared/`.
- Pull before every push, and never force-push. Commit small and often.
- Daniel tags the commit at the freeze (`freeze`), so the held-out run can be traced to exact code.
- These rules go into the repo's CLAUDE.md, so each person's Claude Code follows them.

## Gaps and decisions

All ten gaps are decided.

| # | Gap | Decision | Action and owner |
| --- | --- | --- | --- |
| 1 | Framework | Next.js on Vercel (changed 14 Nov evening, was Gradio on Hugging Face Spaces). The pipeline stays in Python, and the app reads its JSON files. Simple styled cards rather than a polished clinical look | Lane C: deploy a hello app first thing on Sunday and check the public link opens on a phone without signing in |
| 2 | Time and scope | **Must:** Synthea evaluation, keyword baseline with stack-everything merge, saved outputs, both record views, results table with age and sex breakdowns, app, write-up. **Should, in order:** trap notes, omission check, medSpaCy, MTSamples, video. **Defer:** live extraction on the public app, extra integrations, elaborate styling | Whole team: freeze scope tonight. Do not start a Should item while a Must is unfinished |
| 3 | Central table | Version-controlled JSON is the canonical store. The app loads saved records from it. Runtime uploads are temporary, because the hosted app has no permanent file storage | Lane B: define the JSON files. Lane C: make the demo work entirely from those files |
| 4 | Update or conflict | Follow the six compile rules above. In short: an explicit stop or a later dose updates the fact with history kept; silence settles nothing; allergy contradictions stay visible | Lane B: implement the rules. Lane A: write a test case for each rule |
| 5 | Brand names | A brand-to-generic table is a Must. Build it from the full list of brands the Hospital C template can write, not from the brands seen in the working patients, so held-out patients are covered. Freeze it before the held-out run. Unknown names are shown with an "unknown name" flag, never guessed | A and B: agree the table. B owns the code |
| 6 | Synthea suitability | Inspect the real files tonight, then pick a small, fixed set of facts per patient. Any planted trap goes into the answer key too, and is labelled as a change we made | Daniel: build the demo patient and the first 5 working patients on Saturday night |
| 7 | Model budget | Save every extraction and its token usage. Rerun everything after extraction from saved files. One retry only when extraction fails a check. About 600 to 700 calls in total | Lane B: send one test record on Saturday night if there is time. Compare the two models on Sunday morning, record the per-call tokens, recheck the spend limit |
| 8 | Patient identity | Keep one shared synthetic patient ID across hospitals. State in the write-up that matching patients across hospitals is outside scope | Lane A: assign IDs consistently. Lane C: add the limit to the write-up |
| 9 | Public model calls | The public demo works with no live model call: preloaded patients and a saved extraction walkthrough. Live upload stays off, because it would need the extraction prompt rewritten as a Next.js API route. If it is ever switched on, it must have limits | Lane C: make every video shot work without an API key. Never expose the key in the frontend or the repo |
| 10 | Upload formats | UTF-8 CSV for the table format and plain-text TXT for the other two. The brand-name layout is a TXT template, not a third file type. PDFs, images and OCR are future work | A and C: agree the CSV header and supply one example file per hospital format |

A smaller point: "clinical lead" decides the correct answers, but nobody on the team is a clinician. Keep trap answers to cases that are unambiguous on the page.

## Data rules

- Only synthetic or public data. Synthea patients, our typed trap notes and MTSamples.
- No real patient records, even de-identified ones such as MIMIC-IV. The brief says not to use real patient records.
- Code templates write the three hospital formats, not an AI.
- Split by patient: tune on 20 working patients, report on 60 held-out patients. The held-out set has 10 patients in each of six groups (three age bands, two sexes). Decide the split before running anything, and do not change the size after seeing results.
- State in the limits: our templates write records more neatly than real hospitals do, so real records could produce more errors. MTSamples is the small check on this.

## What the brief requires for results

| Requirement | Where it comes from | How we meet it |
| --- | --- | --- |
| Results from test data the model did not see during training | Section 3 | No training. Results come from the 60 held-out patients, never looked at while tuning |
| Baseline score next to our tool's score | Section 3, write-up template | The build-up table |
| At least one failure example with an explanation | Section 3 | Three failure examples |
| Missed cases and false alarms reported separately | Health track | Separate columns in the build-up table |
| Checked across groups such as age and sex | Health track, what judges look for | Age and sex breakdown, now a Must |
| The line "This project is a prototype and is not medical advice." | Rule 7, Health track | In the write-up and on every app tab |
| Honest results, including weak ones | Rule 8, section 6 | Report real numbers. If Synthea scores near 100%, say the templates explain it |
| Every dataset, model, tutorial and AI tool cited with links | Rule 4, section 5 | Credits list. Claude appears twice: as the extraction model and as the coding assistant |

## Future directions

- Handwritten and scanned records.
- Real hospital records with permission, such as the n2c2 datasets (several records per patient, need a data use agreement).
- Matching the same patient across hospitals without a shared ID.
- Patient download with identity checks, security and consent.
- Confidence scores, and training our own model.

## Tonight's checklist

Daniel works alone on Saturday night. The first group is the minimum, in order.

- [ ] Set the record format and the fixed lists from the draft above.
- [ ] Set the folders and file names from "Shared contracts", and write the branch rule into CLAUDE.md.
- [ ] Create the GitHub repo and give all three people access.
- [ ] Download the Synthea sample and open one patient's files.
- [ ] Fix the split: 20 working and 60 held-out, 10 per age and sex group. Commit the two ID lists.
- [ ] Write the three hospital templates and set the CSV header.
- [ ] Build the demo patient: three hospital records and its answer key, with the penicillin allergy, warfarin stopped, the metformin dose change and Panadol in the Hospital C record. Add all four to the drug list and the brand-to-generic table.
- [ ] Generate records for the first 5 working patients.
- [ ] Hand-write the sample file for the demo patient.

Stretch for Saturday night. Whatever is left moves to Sunday morning.

- [ ] Write the answer key script and generate every patient, without opening the held-out records.
- [ ] Build the brand-to-generic table from the Hospital C template's full brand list.
- [ ] Send one test record through the API and recheck the spend limit.

Sunday morning, in a 15-minute call before building.

- [ ] Abby and Theo confirm the record format and the folder names.
- [ ] Theo deploys an empty "hello" Next.js app to Vercel and opens its link on a phone.
- [ ] Open one CSV and one TXT file on Theo's Windows machine to check the UTF-8 encoding.
- [ ] Fill the TBDs in the Frontend tools table.
- [ ] Daniel runs Sonnet 5.5 and Haiku 5.5 on the 5 working patients and picks one (after the call).
- [ ] Run the interview command on this doc.
