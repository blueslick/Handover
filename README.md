![Handover title card](docs/Handover%20Title%20Card%(1).png)

# Handover

**Track:** AI + Health

**Team:** Daniel Tan Sheng Jie, Abby Tan Yi Pei, Theo Keat Yeong

**App:** [https://veritas-ai-hackathon.vercel.app/upload](https://veritas-ai-hackathon.vercel.app/upload) (no sign-in, no API key needed)

**Code:** this repository, [https://github.com/blueslick/Veritas-AI-Hackathon-](https://github.com/blueslick/Veritas-AI-Hackathon-)

**Video:** [https://drive.google.com/file/d/1PJhlY8-J7d06t8G49vlt-VvKKm4yQ2ls/view?usp=sharing](https://drive.google.com/file/d/1PJhlY8-J7d06t8G49vlt-VvKKm4yQ2ls/view?usp=sharing)

***This project is a prototype and is not medical advice.***

**This README is the full version of our one-page submission write-up. It has the same sections in the same order, with the detail the one page had no room for.**

## The problem

The World Health Organization names moving between places of care as [one of three priority areas for medicine mistakes](https://www.who.int/publications-detail/WHO-UHC-SDS-2019.9). In an emergency, a patient may be taken to a hospital that has none of their records and the doctor has to prescribe within minutes, sometimes for a patient who cannot speak. This is why records from other hospitals must be merged correctly. If not, an emergency doctor potentially works with outdated information (e.g. a stopped blood thinner shown as current medication, or an allergy that one hospital recorded and another did not).

## What we built

We built Handover, which merges one patient's records from three hospitals, each formatted differently, into one up-to-date record, allowing a doctor to catch a dangerous allergy or medicine mistake before prescribing.

- **The input** is three hospital records for one patient: a table (CSV file), a free-text doctor's note, and a record that uses brand names such as Panadol.
- **The output** is one record, with allergies and current medicines shown first. Every fact shows its hospital, date and exact quote; stopped medicines and dose changes are marked; when hospitals disagree, both versions are shown with a warning.
- **How it is used:** an emergency doctor or nurse opens the app, types the patient's ID and reads the record in seconds. A GP or pharmacist could use it the same way, but we designed it for the emergency doctor.
- **When something needs checking:** every warning (a disagreement between hospitals, a stopped medicine, a missing dose) has a “Who can confirm this” box listing who could confirm it, such as each hospital involved with an example contact. The hospitals and contacts are made up. These are options, not recommendations: the doctor decides.

**What we assume:** Handover is for after the legal questions are settled: patients have agreed to share their records, hospitals can opt out, and the country has chosen to connect hospitals, as Malaysia is working towards with its [“One Individual, One Health Record” plan](https://www.thestar.com.my/news/nation/2026/06/15/health-ministrys-healthcare-digitalisation-reaches-421-million-users). Handover solves the problem that is left: each hospital writes records differently, and they must be merged without losing a dangerous fact.

Our output follows the FHIR layout used by health record systems. It does not connect to any real national system. The public app only replays saved results: it never calls an AI model, so it needs no sign-in and no API key.

## What we added

**Our own idea.** AI tools that merge records exist (e.g. [Particle Health Snapshot](https://docs.particlehealth.com/docs/particle-snapshot), [Epic's AI summaries](https://fiercehealthcare.com/health-tech/epic-expands-ai-ambitions-agent-platform-cosmos-powered-predictions-and-deeper-workflow), [Evidently](https://amia.org/membership/partners/evidently) and [DrFirst](https://drfirst.com/blog/how-hospitals-reduce-medication-errors)), but we found no published test of how often they get a dangerous fact wrong. We have built that test for Handover. Our question: how often does the merged record get an allergy or a medicine dangerously wrong, compared with a simple keyword tool, and is it equally good for every age group and both sexes?

### How this compares with existing tools

Merging records with AI is not new. Commercial tools in the US already do it (the four linked above). Going by their public pages, they connect to real hospitals and they link each summary line to its source. Handover does not connect to real hospitals, and showing a source for each fact is now standard.

What we could not find, as of 15 November 2026, is a published test of how often these merged records get a dangerous fact wrong. That test is the part we built. It matters because leaving facts out is a common error in AI summaries: in [one study](https://www.techtarget.com/searchhealthit/news/366642890/Agentic-AI-discharge-summaries-linked-to-safety-clinician-wellbeing), as reported by TechTarget, doctors flagged omissions in 25% of AI-written summaries and made-up facts in 2%.

|  | Existing tools | Handover |
| --- | --- | --- |
| Records fetched from real hospitals | Yes | No: records come in as files (the public app replays saved ones) |
| Source shown for each fact | Yes | Yes, and our code checks the quote is really in the record |
| A missing detail, such as a dose | DrFirst's AI fills in missing prescription instructions | Flagged, never guessed |
| Check for facts the AI left out | Not advertised | Omission check (a hint only, see Limitations) |
| Published error rates, missed facts and false alarms separately, by age and sex | None found | Yes |

## How it works

### Data

180 synthetic patients from Synthea's November 2021 sample of 1,163 patients ([download page](https://synthea.mitre.org/downloads)). No real patient records were used. Synthea simulates whole patient lives, so every allergy, illness and medicine is made up but realistic. Code templates, not an AI, wrote each patient as three hospital records, and the correct answers (the answer key) come straight from Synthea. The patients and notes we used:

| Set | Size | What it is for |
| --- | --- | --- |
| Working patients (Synthea) | 20 (P001-P020) | Trying the tool and adjusting the prompt and rules. We could look at these. |
| Held-out patients (Synthea) | 160 (P021-P100 and R001-R080), with 20 per age band (0-19, 20-44, 45-64, 65+) and sex | The only results we report; never looked at while building |
| Typed trap notes | 20 short notes, plus a look-alike of each | Notes we typed ourselves, each hiding one trap; every answer checked by a person |
| MTSamples notes (public) | 12 notes, 84 facts | Real doctors' writing style, labelled by hand; a check on messier records |
| Demo patient | 1 (D001) | Shown in the app and video; built by hand, not scored |

**Who we picked.** Patients alive on 18 Nov 2021 (the last date in the sample) with at least one prescription. We split them by age on that date into four bands (0-19, 20-44, 45-64, 65+) and by sex. A script with a fixed seed (20261114) picked the patients and the split before we ran anything, and the lists were never changed afterwards.

**Why the held-out set is so large.** It is eight times the working set because we do not train a model. Claude is used as it comes, so a few patients are enough to tune on. The held-out set needs to be large so each of the 8 age and sex groups rests on 20 people, not two or three. The script first picked 10 per group plus a reserve batch of 10 more per group. We added the reserve to the held-out set before any working or held-out result existed, so the test stays fair.

**Allergies picked first.** Drug allergies are rare in the sample (59 in 1,163 patients). In each held-out group we took up to 3 patients with a drug allergy first, then the rest at random. This gives 41 held-out patients with a drug allergy: 24 in the first batch and 17 in the reserve batch. Both batches used the same rule; the reserve has fewer because the sample ran out of drug-allergy patients. Because of this oversampling, allergy results are not typical of the whole sample.

**How we cleaned it.** We kept each patient's last 5 years (18 Nov 2016 to 18 Nov 2021): all allergies, current illnesses, current medicines started in that window, medicines truly stopped in that window (a refill is not a stop) and dose changes. Operations and illnesses that had ended were left out. After this trim, 19 of the first 100 patients (P001-P100) have no current medicine; we kept them to test the “no regular medicines recorded” case.

**Turning patients into hospital records.** Code templates, not an AI, write each patient as three hospital records in different styles: a CSV table (Hospital A), a free-text note (Hospital B) and a record using brand names such as Panadol (Hospital C). The app shows them by made-up names: Northfield (A), Riverside (B) and Seri Bayu (C). The correct answer for each patient (the answer key) comes straight from Synthea by a script, and a teammate who did not build it spot-checked it against the original data.

**Planted traps.** Some records hide a planted trap of one of four kinds: a medicine stopped at only one hospital, a dose change, a medicine the latest hospital does not mention, and an allergy one hospital missed.

### The tool

Each hospital record goes through three steps, and the same records also go to a simple keyword tool so we can compare the two. Step 1 is where the AI does the main job: Claude reads each messy hospital record and pulls out every fact. Steps 2 and 3 are safety checks written in code around it, so the merge never quietly picks one hospital over another on an allergy or a current medicine.

- **Extract (AI).** Claude Sonnet 5.5 reads one hospital record at a time. It lists every allergy, medicine, diagnosis and operation in our record format, each with the exact words it was taken from. Every reply is saved, so later steps and reruns never make a new call.
- **Check (code).** Every fact is tested against the record. The quoted words must appear in the record exactly, the drug name and dose must sit inside them, and the status (such as current or stopped) must be one allowed for that type. Brand names become generic names from our brand table (Panadol becomes paracetamol). If any fact fails, the record gets one retry: Claude sees its first answer and the list of problems. A fact that still fails is kept and marked “unverified”, never quietly dropped.
- **Merge (code).** Six fixed rules join the three checked records into one:
    - **Same drug, one fact**: the same drug at several hospitals becomes one fact that lists every hospital.
    - **A stop is a stop**: a later record that says a drug was stopped marks it stopped, and the earlier entry stays in the history.
    - **Dose changes**: a later dose replaces the earlier one, the old dose stays in the history, and the card says “dose changed”.
    - **Silence is not a stop**: a record that doesn't mention a drug leaves it as it was, showing where it was last recorded.
    - **Allergies are never removed**: if one hospital records an allergy and another says “no known allergies”, both are shown side by side with a warning.
    - **Any other disagreement** on an allergy or a current medicine is shown the same way. The tool never picks a winner on an allergy or a current medicine.

The merge rules are tested by six test cases written by a teammate who didn't build them, and the answer key uses its own separate copy of the rules, so scoring never marks the tool against itself.

### What we compare against

- **Keyword search (our baseline).** A word list that looks up drug and allergy names in each record and stacks the three records with no merging. It does not look for diagnoses or operations.
- **medSpaCy.** A free rule-based medical text reader, using the same word lists, also stacked.
- **Microsoft Azure Text Analytics for Health.** A commercial tool, run once after our own held-out results, on allergies and medicines only.

### Which model, and what it costs

We use Claude Sonnet 5.5 (`claude-sonnet-5-5`), picked by a rule we wrote down before we saw the scores. We ran Sonnet 5.5 and Haiku 5.5 (`claude-haiku-5-5`) on the 20 working patients with the same prompt.

The rule compares, in order: fewer missed allergies and current medicines, then fewer false alarms on those, then fewer total misses and false alarms, then wrong statuses and doses. A full tie goes to Sonnet.

On the 20 working patients (this is how we chose, not a result) the two models tied on every measure: 163 of 164 facts matched, 1 missed, 2 false alarms, every dose right and all 8 disagreements shown. So the rule picked Sonnet. Haiku was then run once on the held-out patients as an extra row, and we report both models whichever does better. We never switch models after seeing held-out results.

Costs come from the real token counts of the held-out runs (160 patients, 3 calls per patient, one per hospital record).

| Model | Cost per patient | Cost per 1,000 patients |
| --- | --- | --- |
| Sonnet 5.5 (used) | 4.27 US cents | about $43 |
| Haiku 5.5 (comparison) | 0.29 US cents | about $2.90 |

**Model settings.** Claude 5.5 models don't accept temperature 0 (the setting that usually makes an AI give the same answer every time) or turning thinking off. We send no temperature, use the lowest thinking setting each model accepts and a fixed answer shape, and make results repeatable by saving every reply.

## Results

Every number here comes from the 160 held-out patients, run once on the frozen tool after we stopped changing it. Their answer keys hold 1,668 facts, of which 861 are allergies and current medicines. The numbers are copied from the committed results files in [`outputs/results/heldout/`](https://github.com/blueslick/Veritas-AI-Hackathon-/tree/main/outputs/results/heldout). Our baseline, keyword search, found 752 (45.1%). Handover found 1,655 (99.2%). A **missed** fact is one left out or wrong (a false negative); a **false alarm** is a fact not in the answer key (a false positive).

**In the app:** on the [How we tested tab](https://veritas-ai-hackathon.vercel.app/how-we-tested), tap any planted trap's name to see what we changed in the records and what the right answer is. Open “Details: method, limits, cost” for a cost table comparing Claude Sonnet 5.5 and Claude Haiku 5.5, per patient and per 1,000 patients.

| Method | Missed (of 1,668) | False alarms | Hospital disagreements shown (of 38) |
| --- | --- | --- | --- |
| Keyword search (baseline) | 916 (54.9%) | 1,312 | 0 |
| Handover (Claude Sonnet 5.5) | 13 (0.8%) | 47 | 38 |
| Handover on Claude Haiku 5.5 (0.29 US cents per patient) | 16 (1.0%) | 60 | 38 |

- **Allergies and current medicines:** Handover missed 4 of 861 and raised 42 false alarms; keyword search missed 109. All 4 misses are the same mistake: a combination medicine read as its two ingredients (see [Where it fails](https://github.com/blueslick/Veritas-AI-Hackathon-#where-it-fails)). Haiku misses the same 4.
- **Planted traps:** a medicine stopped at only one hospital, caught 72 of 74 (keyword search 0); a dose change, 54 of 54 (keyword search 1).
- **Typed trap notes:** on 20 short notes we wrote, each hiding one trap, the tool got 18 traps and all 20 look-alike notes right.
- **Age and sex:** all 8 groups scored between 97.9% and 100% of facts found. Weakest were men aged 65+ (6 missed, 13 false alarms of 282 facts). Groups of 20 are too small to prove it is equally good for everyone.
- **Doses:** every dose Handover reported matched the answer key (437 checked, 0 wrong).
- **Commercial tool:** Microsoft Azure Text Analytics for Health, run afterwards on the same allergies and medicines, is compared in [its own table below](https://github.com/blueslick/Veritas-AI-Hackathon-#commercial-tool-added-afterwards).

### What each step adds

Rows 1 to 3 are comparisons that use no AI. Rows 4 to 7 build our tool up one step at a time, so they show what each part does. Row 8 is the full tool on a cheaper model. “Stacked” means every hospital's facts are listed with no merging.

| Row | Method | Missed (of 1,668) | False alarms | Disagreements shown (of 38) |
| --- | --- | --- | --- | --- |
| 1 | Keyword search, stacked (baseline) | 916 | 1,312 | 0 |
| 2 | medSpaCy, stacked | 511 | 1,269 | 0 |
| 3 | Keyword search + our six merge rules | 916 | 297 | 10 |
| 4 | Claude, plain lists, stacked | 422 | 2,272 | 0 |
| 5 | Claude with status labels, stacked | 48 | 2,314 | 0 |
| 6 | Claude with labels + Check, stacked | 9 | 2,275 | 0 |
| **7** | **Full tool: Claude + Check + six merge rules** | **13** | **47** | **38** |
| 8 | Full tool on Claude Haiku 5.5 (cheaper model) | 16 | 60 | 38 |

- **Claude reads, the rules tidy.** Adding Claude and the Check step (rows 4 to 6) cuts misses from 916 to 9, but stacking every hospital's facts leaves over 2,000 false alarms. The six merge rules (row 7) bring those down to 47, and only the full tool shows every disagreement. Misses rise a little from row 6 to row 7 (9 to 13) because the merge must keep one status per medicine, and in a few split-combination cases it kept the wrong one (failure example 2).
- **Not all errors are the tool's.** 4 of the 13 misses and 4 of the 47 false alarms come from a double space in four answer-key diagnosis names, copied from Synthea; the tool spelled them correctly. We left the keys and scores unchanged, because keys are never edited after the freeze, so they still count as misses.
- **Held-out vs working.** Results are a little worse than on the 20 working patients (13 misses in 1,668 facts against 1 in 164, and about three times as many false alarms per patient). We report them as they are.

### By age group and sex

Handover (row 7) against the keyword baseline (row 1), all facts. Each group has 20 patients.

| Group | Key facts | Handover: missed | Handover: false alarms | Keyword: missed | Keyword: false alarms |
| --- | --- | --- | --- | --- | --- |
| Age 0-19, female | 198 | 0 | 2 | 82 | 208 |
| Age 0-19, male | 136 | 2 | 9 | 72 | 130 |
| Age 20-44, female | 191 | 0 | 4 | 95 | 204 |
| Age 20-44, male | 165 | 1 | 5 | 74 | 159 |
| Age 45-64, female | 271 | 1 | 5 | 136 | 258 |
| Age 45-64, male | 189 | 1 | 6 | 110 | 118 |
| Age 65+, female | 236 | 2 | 3 | 168 | 112 |
| Age 65+, male | 282 | 6 | 13 | 179 | 123 |

Handover's weakest groups were men aged 65 and over (6 missed, 13 false alarms; they have the most facts per patient) and males aged 0-19 (9 false alarms among 143 facts listed, the lowest share correct). No group was far behind, but with 20 patients per group one patient can move a group's numbers a lot, so this does not prove the tool is equally good for everyone.

### Planted traps and typed trap notes

Some records hide a planted trap (257 scored). Two kinds separate the methods: a medicine stopped at only one hospital (Handover caught 72 of 74, keyword search 0) and a dose change (54 of 54 against 1 of 54). The other two kinds, a medicine the latest hospital doesn't mention (62 of 62) and an allergy one hospital missed (67 of 67), were caught by keyword search too, so they are not evidence for our tool. 3 more traps were not scored because a later record had overtaken them. We tightened the dose-change scoring rule (right dose, and no old dose left as current) after the first trap run, before reporting.

**Typed trap notes.** We also typed 20 short notes, each hiding one trap, plus a look-alike of each where the fact is really true (not held-out patients; a person checked every expected answer by hand). The tool got 18 of the 20 traps and all 20 look-alikes right, with every dose correct. The two it got wrong were “We will consider warfarin” and “If her pain returns” (paracetamol): it listed both as planned medicines, where our answer key records no medicine.

### Commercial tool (added afterwards)

After seeing our own held-out results, we also ran Microsoft Azure Text Analytics for Health (a commercial tool that reads medical text) once on the same 160 held-out patients. It reads allergies and medicines only, so this table uses the 1,157 answer-key facts of those kinds.

| Method | Missed (of 1,157) | False alarms | Hospital disagreements shown (of 38) |
| --- | --- | --- | --- |
| Microsoft Azure | 141 (12.2%) | 1,124 | 0 |
| Microsoft Azure + our six merge rules | 144 (12.4%) | 168 | 38 |
| Handover (Claude Sonnet 5.5) | 9 (0.8%) | 43 | 38 |

On the same 1,157 facts, medSpaCy missed 0 but raised 1,269 false alarms and keyword search missed 405 with 1,312. On allergies and current medicines (861 facts), Azure missed 74 either way and Handover 4.

Part of Azure's gap comes from us. Our rule that ignores “conditional” items also dropped “as needed” medicines, which explains 54 of Azure's 141 misses (we did not look into the other 87). 91 drug names it found are not in our lists, so they gave no fact. No reply carried a “past” or “future” label, so a medicine counts as stopped only when its line says “stopped” or “discontinued”. We also made one correction to our translation rules on the 20 working patients before this run, and our tool was tuned on these three record layouts while Azure was not. So this compares Azure as we translated its output, not Azure at its best.

### Omission check

The omission check searches each record for drug and allergy words that the AI didn't extract. Across 480 records it raised 173 “possibly missed” hints, and only 1 pointed at one of Handover's 13 misses. It cannot see diagnoses, and a split combination still looks present by name, so it missed the mistakes that actually happened. We show it as a hint for the doctor, not a safety net.

### Second model and cost

On the same patients, Claude Haiku 5.5 missed 16 facts and raised 60 false alarms (Sonnet: 13 and 47) at 0.29 US cents per patient instead of 4.27. 27 of Haiku's 480 first readings failed our format check (for example a drug name not written as a generic); the Check step cleaned them up. Sonnet stays the main model: it was picked on the working patients before any held-out result, and we never switch after seeing them.

### Where it fails

9 of the 13 misses and 43 of the 47 false alarms come from one cause: a combination medicine written as “X and Y” and read as two medicines. 4 more misses are a double space in four answer-key names, not tool mistakes; we left them counted as misses. Overall, harm is low, since the doctor still sees both names and the quote. We did not fix it because the tool was frozen before testing.

Three examples from the held-out run, chosen after scoring. They share one cause, shown three ways. The longer version, with every quote, is in [our failure examples file](https://github.com/blueslick/Veritas-AI-Hackathon-/blob/main/docs/failure_examples.md). The quotes are from synthetic records.

- **A premixed insulin is shown as two insulins (patient P092).** Hospital B's note said “She is on insulin isophane and insulin regular twice a day.” That is one premixed product, but the tool listed two separate insulins and no combined one: 1 missed and 2 false alarms. The mistake happened at the first step, reading the note; Check and Merge passed it on.
- **A stopped medicine looks current again (P051).** Hospital A recorded paracetamol as stopped. A later Hospital B note said “He takes paracetamol and hydrocodone when needed.” The tool split this into a new “paracetamol, current” entry, and the merge rule “the latest date wins” let it override the stop, which stays visible in the history. This is one of the 2 planted “stopped at one hospital” traps the tool missed.
- **An opioid is listed twice (P066).** Hospital B's note said “He takes paracetamol and oxycodone when needed.” It had a similar sentence about hydrocodone. The tool correctly listed both combination painkillers from Hospitals A and C, but also listed oxycodone, hydrocodone and paracetamol on their own from Hospital B: 3 false alarms.

**What they have in common.** Hospital B's template writes a combination medicine as “X and Y”. The model reads familiar pairs as one product (amoxicillin and clavulanate, 7 of 7 notes) but splits less familiar ones (paracetamol and hydrocodone 8 of 8, insulin 5 of 5). Haiku makes the same mistakes. A fix we did not make, because the tool was frozen: when two facts come from one quote and together match a combination in our drug list, join them. The same mistake can be seen on [working patient P012 in the app](https://veritas-ai-hackathon.vercel.app/?id=P012).

## Limitations

- **Records neater than real ones.** Our templates are tidier than real hospitals, and the “X and Y” wording, which caused most of our errors, is ours; real notes may differ. On 12 public MTSamples notes in real doctors' style (84 allergy and medicine facts, not part of the held-out test), Handover found only 35 of 84 facts, missed 49 and raised 58 false alarms. 48 of the 49 misses were medicines or allergies the tool found and quoted but could not give a standard name, because their drug names are not in our lists; the tool marks these as unknown names instead of guessing.
- **Synthetic patients only.** No real patient records were used, so we do not know how well it works on real ones.
- **The omission check is only a hint.** Our second pass that looks for drug and allergy words the AI left out pointed at only 1 of the 13 misses. It cannot see missed diagnoses, and it cannot spot a combination medicine read as two, because both drug names do appear in the output.
- **Small groups.** With 20 patients per age and sex group, and only 41 patients with a drug allergy, small gaps between groups may be chance.
- **Long-term medicines untested.** We kept only five years of history, so current medicines started before November 2016 (for example a long-term EpiPen or antihistamine) were left out of both the records and the answer keys. Scoring is still fair, because the tool and the answer key see the same records, but our test says little about medicines taken for many years.
- **Only part of a medical record.** The tool reads allergies, medicines, diagnoses and operations. Lab results, vital signs, scans and the doctor's plans are not covered, so it is not a full summary of the patient.
- **A combination medicine is read as two medicines.** When one product contains two medicines and both names appear on one line, the tool records them as two separate medicines. The doctor still sees both drug names but isn't told that they come from one product. This explains all 4 of Handover's misses on allergies and current medicines.
- **Four answer-key names have a typing slip.** Four answer-key diagnosis names contain a double space copied from Synthea, so the tool's correct spelling didn't match (4 misses and 4 false alarms). We left the keys unchanged, because keys are never edited after the freeze.
- **A weak baseline on allergies.** Our keyword search does not recognise “NKA” (short for no known allergies), so it can never flag an allergy recorded at one hospital against “NKA” at another, and our lead over it is a little larger than against a better word list.
- **Two plain-list files break the record format.** In row 4 of the step-by-step table (Claude reads each record, with no Check step and no merging), 2 of the 480 files fail our format check. We scored them as written, because that row has no Check step by design. This lowers row 4 slightly.
- **Answers can vary slightly.** Claude can give a slightly different answer to the same record. We saved every reply, and all results and the app replay those saved replies, but we ran the held-out patients once, so a fresh run could differ a little.
- **One shared patient ID assumed.** The app finds a patient by one ID used at every hospital; matching patients without it is not built.
- **Test patients less realistic than real ones.** A former pharmacist reviewed the app on 16 November and found our test patients less realistic than real records. Combination medicines have no strength written, one patient has asthma inhalers but no asthma in his problem list, and the demo patient lists as-needed paracetamol. These come from the synthetic data and from how we trimmed it and wrote the hospital records, so our results show how well the tool reads these records, not real ones. The demo patient is also simpler than a real patient with a heart condition, who would usually be on more medicines. Two more things made the test easier than real life: our drug list was built from every medicine name in the dataset, so the tool never met a name it did not know, and we wrote how often each medicine is taken ourselves, in a few fixed phrases. A clinician should review the test records next.

## Next steps

- **Messier records:** test on scanned and handwritten notes, and more public sample notes like MTSamples, since our templates write more neatly than real hospitals do.
- **Fix combination medicines.** When two facts come from one quote and together match a combination medicine in our drug list, join them into one. This is the cause of most of our errors.
- **A bigger drug list.** Most misses on the real-style MTSamples notes were drug names missing from our lists, so real notes need a much larger list.
- **A cheaper mix of models.** Haiku reads every record, and Sonnet rereads only the records that fail the Check step. This could cost close to Haiku while keeping Sonnet's accuracy where it matters. We have not built or tested it.
- **More kinds of facts.** Lab results, vital signs (such as blood pressure) and the doctor's plan, which the tool does not read yet.
- **Matching patients across hospitals.** Finding the same patient at each hospital when they do not share one patient ID.
- **Mark a warning as settled.** Let the doctor record that a disagreement was checked and how, which the app cannot do yet.

## Sources

Every dataset, model, library and AI tool we used, with links, is listed in [docs/sources.md](https://github.com/blueslick/Veritas-AI-Hackathon-/blob/main/docs/sources.md). Who was responsible for which part is in [docs/credits.md](https://github.com/blueslick/Veritas-AI-Hackathon-/blob/main/docs/credits.md).

Existing tools and the study we compared against (public pages, read 15 November 2026):

- [Particle Health Snapshot](https://docs.particlehealth.com/docs/particle-snapshot), with its [AI summary](https://docs.particlehealth.com/docs/particle-snapshot#longitudinal-patient-summary)
- [Fierce Healthcare on Epic's AI summaries](https://fiercehealthcare.com/health-tech/epic-expands-ai-ambitions-agent-platform-cosmos-powered-predictions-and-deeper-workflow)
- [Evidently (AMIA partner page)](https://amia.org/membership/partners/evidently)
- [DrFirst medication history](https://drfirst.com/blog/how-hospitals-reduce-medication-errors)
- [TechTarget news report on a JAMA Network Open study of AI-written hospital discharge summaries](https://www.techtarget.com/searchhealthit/news/366642890/Agentic-AI-discharge-summaries-linked-to-safety-clinician-wellbeing)
- [World Health Organization, Medication safety in transitions of care](https://www.who.int/publications-detail/WHO-UHC-SDS-2019.9) (the source for The problem)

## Folder guide

| Folder | What is in it |
| --- | --- |
| `app/` | The website (Next.js). It only reads saved results; it never calls a model. |
| `pipeline/data/` | Synthetic patients, hospital records, answer keys and the scripts that make them |
| `pipeline/tool/` | The tool itself: extract, check, merge and the saved-reply layer |
| `pipeline/eval/` | Scoring, the baselines and the omission check |
| `outputs/` | Saved model replies, merged records, baseline records and results |
| `shared/` | The record format, folder and file names, drug list and brand-name table |
| `docs/` | Sources, credits, decisions log, failure examples |

## Run the app on your own computer

You need Node.js 20 or newer.

```
cd app
npm install
npm run dev
```

Then open [http://localhost:3000](http://localhost:3000). No API key is needed: the app shows saved results only.

To rebuild the results file for the “How we tested” tab from the committed held-out totals, run `node scripts/make-results.mjs` from `app/`.

The pipeline (Python 3.11 or newer) needs the Synthea download described in [`pipeline/data/README.md`](https://github.com/blueslick/Veritas-AI-Hackathon-/blob/main/pipeline/data/README.md), and an Anthropic API key to make new model calls.

***This project is a prototype and is not medical advice.***
