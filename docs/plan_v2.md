> Where this disagrees with the Handover plan (`docs/Handover_Pipeline_and_Frontend_Plan.md`), the Handover plan wins. See its 'Changes since plan v2'.

# Project Plan: Safe Record Conversion for Hospital Transfers

Veritas AI International High School Hackathon 2026 · AI + Health track · Our own idea

**Working title:** Handover (change it if you like)

**Deadline:** Monday 16 November, 12:59 PM Malaysia time (11:59 PM ET Sunday). Aim to submit a first version on Sunday night.

---

## 1. The project in one paragraph

When a patient moves between hospitals, their history arrives as free-text notes, scans or handwriting. Countries building shared health records have to convert those notes into a standard format, and a careless conversion puts wrong allergies and medicines into a record every hospital will trust. We build a tool that converts a clinical note into a standard record, and we test how often it gets dangerous facts wrong using a set of trap notes we wrote ourselves.

**Our main takeaway for judges:** converting notes is easy to do and easy to do unsafely. We measure the unsafe part.

---

## 2. Who it is for

- **User:** a doctor in an emergency department receiving a patient transferred from another hospital.
- **Moment:** the patient has just arrived, and the doctor needs their allergies and current medicines before prescribing anything.
- **What changes for them:** a one-page record with the critical facts at the top, each linked to the sentence it came from, and a warning on anything the tool could not verify.

Keep this user in every part of the write-up and video. Do not drift toward "the ministry" or "the health system".

---

## 3. Why the problem is real

Use two or three of these in the write-up, with the links in section 14.

- Malaysia is rolling out electronic records across public hospitals, with the remaining hospitals scheduled by end 2029 and RM1 billion announced in August 2026.
- Singapore has had a national record since 2011, yet only about 30% of private providers were contributing by late 2024, and a 2026 law now makes it compulsory.
- Two Singapore private hospitals blamed delays on fitting their existing records to the national format.
- A US fact sheet notes that some record systems file a medication reaction as an allergy while others file it as a side effect.
- A large study of AI-written clinical notes measured invented content at about 1.5% of sentences and left-out content at about 3.5%.

**What we do not claim:** we do not solve security, cost, legal liability or patient trust, and we do not claim compatibility with any country's real system.

---

## 4. What we are building

### The pipeline

1. A note goes in: typed text, or a scanned or photographed page.
2. A language model fills in a standard record. Every fact gets a status label and a supporting quote from the note.
3. Our code checks each quote appears word for word in the note (the evidence check).
4. The doctor sees a one-page record: critical facts first, unverified facts flagged.
5. For testing, the same notes go through a keyword baseline, and both outputs are scored against our answer key.

### The standard record

| Record type | Fields | Danger tier |
|---|---|---|
| Allergies | substance, reaction, status, quote | Critical |
| Medicines | name, dose, frequency, status, quote | Critical |
| Diagnoses | condition, status, quote | Other |
| Past operations | procedure, year, quote | Other |

The layout follows the international FHIR standard's allergy, medication and condition record types. Say "our output follows the FHIR layout". Do not claim it plugs into a specific national system.

### Status labels

| Label | Meaning | Example |
|---|---|---|
| Current | True of the patient now | "on metformin 500 mg bd" |
| Stopped / past | Was true, no longer | "warfarin stopped 2 months ago" |
| None recorded | Explicitly absent | "no known drug allergies" |
| Suspected | Not confirmed | "?pneumonia" |
| Family history | About a relative | "mother has breast cancer" |
| Planned | Not started yet | "start amoxicillin if fever persists" |
| Side effect | A reaction that is not an allergy | "nausea with codeine" |

### The evidence check

- The model must return the exact words from the note that support each fact.
- Our code searches the note for that quote. This is a plain text search, with no AI.
- If the quote is missing, the fact is marked "unverified".
- **Catches:** invented facts.
- **Does not catch:** misreadings, where the quote is real and the conclusion is wrong. The status labels and trap set cover those.
- **Limit with scans:** if the model misreads handwriting, the quote matches its own misreading. State this in the write-up.

### The two danger tiers

- **Critical:** allergies, current medicines, doses and frequency. These decide what the doctor prescribes in the next hour.
- **Other:** everything else.
- Report the two error rates separately. The critical rate is the headline number.
- In the tool, any unverified critical fact shows a banner: confirm with the patient or the sending hospital.

---

## 5. The keyword baseline

A simple program with word lists and three rules, and no understanding of sentences.

- Any drug name in the note is recorded as a current medicine.
- Any disease name in the note is recorded as a current diagnosis.
- A drug name near "allergy", "allergic" or a reaction word is recorded as an allergy.

Build the word lists from the drugs and diseases that appear in our test notes, plus common ones. Write this first, because it is quick and the brief requires it.

---

## 6. Data

| Set | What | Size | Purpose |
|---|---|---|---|
| **Trap set** | Short notes we write, each hiding one trap, plus a twin where the fact is true | 80 notes | The main test |
| **Real-clinician notes** | Samples from MTSamples (public domain, on Kaggle), trimmed to the relevant sections | 12 notes | Shows it works on writing we did not produce |
| **Handwritten scans** | 15 of the trap-set notes copied out by hand and scanned or photographed | 15 pages | Typed versus handwritten comparison, with no new answer key needed |

### Rules for our data

- Every patient is invented. Nothing is based on a real person or a real document.
- Humans write the trap notes. Do not have an AI write them.
- Borrow real phrasing from MTSamples so we can say the wording is realistic.
- One person writes a note, a different person writes its answer key.
- Give patients a spread of ages (child, adult, elderly) and both sexes, and record this for each note.
- **Split the trap set in half.** Use 40 notes while adjusting the tool. Keep 40 untouched for the final score. Decide the split before running anything.

---

## 7. The trap set

Five traps and five twins for each of eight types: 80 notes.

| # | Trap type | Trap example | Twin example (fact is true) | Wrong answer |
|---|---|---|---|---|
| 1 | Negation | "No known drug allergies." | "Allergic to penicillin, rash." | Records an allergy |
| 2 | Family history | "Mother has type 2 diabetes." | "Has type 2 diabetes." | Gives the patient the condition |
| 3 | Stopped medicine | "Warfarin stopped two months ago." | "On warfarin 3 mg daily." | Lists it as current |
| 4 | Suspected | "?TB, sputum sent." | "TB confirmed on sputum." | Records it as confirmed |
| 5 | Planned or conditional | "Start amoxicillin if fever persists." | "On amoxicillin 500 mg tds." | Lists it as being taken |
| 6 | Side effect versus allergy | "Nausea with codeine." | "Anaphylaxis to codeine." | Records an allergy |
| 7 | Ambiguous shorthand | "MS" in a heart note | "Multiple sclerosis" written out | Picks the wrong meaning |
| 8 | Dose and units | "0.5 mg", "mcg", per-kilogram doses in children | A plain "5 mg" | Records the wrong dose |

Each note should be three to six lines, so the trap sits inside realistic surrounding text.

### Scoring each note

- **Correct:** matches the answer key, including the status label.
- **Fell for the trap:** recorded something untrue. This is a false alarm.
- **Missed:** left out or mislabelled a real fact. This is a missed case.

---

## 8. The measured improvement

- **Version 1:** the tool outputs flat lists (medicines, allergies, diagnoses) with no status labels.
- **Version 2:** the tool must give every fact a status label.

Run both on the untouched 40 notes and report the change in critical errors. This is the "one improvement, measured" the brief's schedule asks for.

---

## 9. Results we will report

Fill this in with real numbers only. Report weak results as they are.

| Measure | Keyword baseline | Tool v1 (no labels) | Tool v2 (labels) |
|---|---|---|---|
| Critical errors | | | |
| Other errors | | | |
| Missed facts | | | |
| Invented facts | | | |
| Per trap type (8 rows) | | | |

Also report:

- **By note type:** typed trap notes, MTSamples notes, handwritten scans.
- **By age group:** child, adult, elderly.
- **Evidence check:** wrong facts it flagged, and correct facts it flagged by mistake.
- **Failure examples:** at least three, each with the note, the wrong output and our guess at why.

---

## 10. Scope

| Priority | Item |
|---|---|
| **Must** | Extraction into the standard record |
| **Must** | Keyword baseline |
| **Must** | Trap set, answer key and held-out split |
| **Must** | Status labels, evidence check, two danger tiers |
| **Must** | Write-up with the results table and failure examples |
| **Should** | Handwritten scan group |
| **Should** | Age-group breakdown |
| **Should** | Two-minute demo video |
| **Stretch** | Brand-name to generic-name conversion for drugs in our notes |
| **Cut** | Shared database, patient identity matching, security features |

**If we fall behind, cut in this order:** stretch item, handwritten scans, MTSamples notes, video. Never cut the baseline, the held-out split or the failure examples.

---

## 11. Schedule

Times are Malaysia time. Adjust the blocks to when you actually start, but keep the checkpoints.

### Block 1: Saturday, as soon as possible (about 2 hours)

- Agree the standard record and status labels in section 4.
- Get a free model API key working in a Colab notebook with one test note.
- Write the first 10 trap notes and their twins.
- **Checkpoint:** one note goes in and a record comes out.

### Block 2: Saturday evening (about 3 to 4 hours)

- Build the keyword baseline.
- Build tool v1 (flat lists) and the scoring code.
- Finish 40 of the 80 trap notes and their answer keys.
- **Checkpoint:** baseline and v1 both produce scores on the first notes. If the data or API still is not working after 30 minutes of trying, change the tool or model, not the idea.

### Block 3: Sunday morning (about 4 hours)

- Finish all 80 trap notes and answer keys. Fix the held-out split.
- Build v2 (status labels) and the evidence check.
- Hand-copy and scan the 15 handwritten notes.
- Trim and label the 12 MTSamples notes.
- **Checkpoint:** v2 runs on the 40 working notes.

### Block 4: Sunday afternoon (about 3 hours)

- Final run on the 40 held-out notes: baseline, v1, v2.
- Run the handwritten and MTSamples sets.
- Fill in the results table. Pick the failure examples.
- **Checkpoint:** results table complete. No more changes to the tool after this run.

### Block 5: Sunday evening (about 3 to 4 hours)

- Write the one-page write-up.
- Record the demo video.
- Team walk-through: each person explains every part of the notebook aloud.
- **Submit a first version tonight.**

### Block 6: Monday morning, before 12:59 PM

- Open every link in a private window.
- Check names, emails and schools.
- Resubmit only if something is fixed or improved.

---

## 12. Roles

| Role | Owns |
|---|---|
| **Clinical lead** (knows healthcare best) | Writes most trap notes, decides the correct answers, picks failure examples |
| **Build lead** (has trained models before) | Notebook, model calls, baseline, evidence check, scoring code |
| **Evidence and story lead** | Answer keys for notes they did not write, handwritten scans, write-up, video, credits |

Everyone reviews the final notebook together. The rules require the whole team to understand every part.

---

## 13. Rules checklist

- [ ] Team of one to three, every listed member contributed.
- [ ] All work done within the hackathon window.
- [ ] AI does the main job: the model converting notes is the core.
- [ ] Only public or invented data. No real patient records, no real documents scanned.
- [ ] One track: AI + Health.
- [ ] Write-up contains this line exactly: "This project is a prototype and is not medical advice."
- [ ] Baseline score reported next to our tool's score.
- [ ] Results come from the 40 held-out notes.
- [ ] Missed cases and false alarms reported separately.
- [ ] Results broken down by age group and note type.
- [ ] At least one failure example with an explanation.
- [ ] "What we added" says: Our own idea.
- [ ] Credits list every dataset, model, tutorial and AI tool with links, including Claude.
- [ ] Notebook saved with outputs visible.
- [ ] API key removed from the shared notebook.
- [ ] Every link opens in a private window without signing in.

---

## 14. Write-up outline

Follow the brief's template. About one page.

- **The problem:** the transfer moment and why wrong conversions are dangerous. Two facts from section 3.
- **What we built:** note in, standard record out, with labels, quotes and warnings.
- **What we added:** Our own idea. The trap set, the evidence check and the danger tiers.
- **How it works:** the three data sets with counts, how we wrote and labelled them, which model and why.
- **Results:** the table, the improvement from v1 to v2, the breakdowns, three failure examples.
- **What we'd do next:** patient identity matching, real handwritten records with permission, standard drug codes.
- **Sources:** everything below plus tools used.

### Related work and facts to cite

- Malaysia's rollout: https://codeblue.galencentre.org/2026/02/moh-to-integrate-90000-medical-imaging-records-into-mysejahtera-dzulkefly/
- Malaysia's RM1 billion: https://www.thevibes.com/articles/news/126758/rm1b-health-digital-push-to-mean-faster-treatment-better-access-for-malaysians
- Singapore's law and participation: https://www.synapxe.sg/news/national-programmes/health-information-bill and https://captaincompliance.com/?p=11046
- Singapore hospitals and format alignment: https://www.singaporelawwatch.sg/Headlines/new-law-proposed-to-mandate-sharing-patients-info-among-healthcare-providers
- Allergy versus side effect across systems: https://www.pewtrusts.org/es/research-and-analysis/fact-sheets/2016/11/electronic-health-records-patient-matching-and-data-standardization-remain-top-challenges?amp=1
- Invented and omitted content in AI clinical notes, and converting notes to FHIR: https://arxiv.org/pdf/2604.21076 (read the original studies it cites before quoting numbers)
- Negation benchmark for clinical documents: https://arxiv.org/html/2401.14490v1
- MTSamples dataset: https://www.kaggle.com/datasets/tboyle10/medicaltranscriptions

---

## 15. Demo video outline (up to 2 minutes)

| Part | Length | Show |
|---|---|---|
| The problem | 15 s | The doctor, the transferred patient, one sentence on the risk |
| The demo | 60 s | A trap note going in, the baseline getting it wrong, our tool's record with labels, quotes and a warning banner |
| How it works | 30 s | The three data sets, the results table, baseline versus our tool |
| Next steps | 15 s | One failure example and what we'd do next |

A screen recording with a voice-over is enough.

---

## 16. Risks and what to do

| Risk | Response |
|---|---|
| The model scores near 100% on our traps | Make the traps harder and add the MTSamples and handwritten sets. If it still scores high, say so and focus on the failures that remain. |
| Judges ask if our notes are realistic | Point to phrasing borrowed from MTSamples and to the MTSamples results. |
| API limits or errors | Run notes in small batches and save outputs as you go. Have a second free model as a fallback. |
| Handwriting results are poor | Report them. A typed-versus-handwritten gap is a finding. |
| Running out of time | Follow the cut order in section 10. |
| Team cannot explain the code | Do the walk-through in Block 5. Keep the notebook short and commented. |

---

## 17. Limits to state in the write-up

- Our trap notes are written by us, so they reflect the traps we thought of.
- Our notes are in English and use common international shorthand. We did not test Malaysian hospital notes.
- The evidence check catches invented facts, not misread ones.
- The test set is small, so percentages move a lot with each note.
- This project is a prototype and is not medical advice.
