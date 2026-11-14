> Where this disagrees with the Handover plan (`docs/Handover_Pipeline_and_Frontend_Plan.md`), the Handover plan wins. See its 'Changes since plan v2'.

# Handover: Hackathon Project Plan v2 (summary)

Veritas AI International High School Hackathon 2026 · AI + Health track · Our own idea

Full plan with workflow diagram: https://claude.ai/artifact/B5aEBNMNR6DmZBgFxVYY9n

This replaces v1 (single-note conversion). The "Master doc" in this project still holds v1 and is out of date.

**Deadline:** Monday 16 November 2026, 12:59 PM Malaysia time (11:59 PM ET Sunday).

## The project

A web app that compiles one patient's records from several hospitals, each in a different format, into one standard record for an emergency doctor. We then measure how often that record gets dangerous facts wrong.

**The question:** when one patient's records from several hospitals are compiled into a single record, how often does a dangerous fact come out wrong, which kinds of fact, and for which patients?

**User:** an emergency doctor seeing a patient with records at three hospitals, before prescribing. A shared national record is the motivation and the opening hook, not the user.

## Workflow

1. **Upload.** Hospital staff at A, B, C upload records in three formats: a table with its own column names, a free-text note, a brand-name layout.
2. **Extract (language model via API).** Standard record: allergies, medicines, diagnoses, operations. Each fact gets a status label and a supporting quote.
3. **Check (our code).** Quote appears in the source (case and spacing normalised), drug name is on a real drug list, a current medicine has a dose. One retry on failure, then flag.
4. **Omission check (our code, added 14 Nov).** Scan each source record for drug-list names and allergy words. Anything found in the source but missing from the extracted record gets a "possible missed fact" warning. This covers the gap the quote check leaves: it only checks facts the model wrote, not facts it left out.
5. **Compile (our rules).** Remove duplicates, newest fact wins, conflicts shown side by side with a warning.
6. **Store.** One row per fact in a central table, tagged with hospital and date.
7. **Look up.** Doctor types a patient ID and sees the compiled record, critical facts first.

Status labels: current, stopped, none recorded, suspected, family history, planned, side effect.

## Danger tiers

- **Critical:** allergies, current medicines, dose, frequency. Headline number.
- **Other:** diagnoses, past operations.
- Report the tiers separately, and missed facts separately from false alarms.
- A critical fact that is unverified, conflicting or missing a dose gets a warning banner. The app never silently picks a winner.
- The tiers are the team's judgment and do not cover severity inside a tier.

## Data

| Set | Size | Tests | Answer key |
|---|---|---|---|
| Synthea patients, each split across three hospital formats by our code | 40 patients | Extraction and compiling | Synthea's original record, converted by a script |
| Typed trap notes (family history, suspected, planned, side effect vs allergy, ambiguous shorthand) | 20 notes | Traps Synthea lacks | Written by a different teammate |
| MTSamples | 12 notes | Extraction on real clinicians' writing | Labelled by hand |
| MIMIC-IV Clinical Database Demo (option, not decided) | up to 100 real de-identified patients, open access, no free-text notes | Compiling on real medication histories | Its own prescriptions and diagnoses tables |

- Code templates write the hospital formats, not an AI.
- Split by patient: tune on 20, report on the other 20.
- Compile traps: stale fact, duplicate (brand vs generic), conflict, dose change.

## Testing

Build-up table on the 20 held-out patients, each row with critical errors, other errors, missed facts and false alarms:

1. Keyword baseline with a stack-everything merge
2. medSpaCy (moved to Should on 14 Nov)
3. Model, plain lists
4. + status labels
5. + checks and repair
6. + omission check
7. + compile rules

Scoring rules: a match is the same drug (generic name) with the same status; dose is its own critical field; a stopped medicine listed as current is one critical false alarm; a version with no labels is scored as all "current"; a duplicate or an unflagged conflict is one error each.

Also report by trap type (as counts), hospital format, age group, sex, and three failure examples. Report how many missed facts the omission check flagged, and how many of its warnings were false.

## Scope

- **Must:** Synthea data and answer key, extraction, quote check, compile rules, central table, both baselines, held-out results, danger tiers, failure examples, two-screen app (Gradio), write-up.
- **Should:** medSpaCy comparison, omission check, drug-name check, missing-dose flags, repair loop, typed trap notes, MTSamples, age and sex breakdown, demo video.
- **If time:** MIMIC-IV demo patients, identity matching side test.
- **Future directions:** n2c2 datasets (real longitudinal records, need a data use agreement), handwritten records, real hospital data, confidence scores, training our own model, patient download and identity verification.
- **Cut order:** identity matching, MIMIC-IV demo, repair loop, medSpaCy, video.

## Decisions made on 14 November

- Language model through an API, no training. Allowed by rule 4 and the FAQ in the brief.
- No confidence scores.
- Digital records first, handwriting later.
- medSpaCy moved from If time to Should.
- Omission check added.
- Patient download is out of scope for the hackathon.
- The pitch: "Everyone is building tools to compile patient records. We built one, then built a test that shows where compiling goes dangerously wrong."

## Open checks

- Synthea needs Java or its ready-made sample download; export fields not yet checked.
- Free API request limits not yet checked.
- Which model: Gemini free tier, or paid Claude API.
- Links to the Malaysia and Singapore facts carried over from v1 have not been verified.
