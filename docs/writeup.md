# Handover: write-up

Veritas AI International High School Hackathon 2026 · Track: AI + Health · Team: Abby Tan, Daniel Tan, Theo

> Skeleton only (T30). Each section names its owner and what goes in it. Replace every line in italics. Target length: about one page. Numbers go in only after the held-out run (T37); never type a result by hand.

This project is a prototype and is not medical advice.

## The problem

*Owner: Daniel (T46b). About 4 sentences.*

- *The user: an emergency doctor, at the moment a patient with records at three hospitals arrives.*
- *Why a wrong merged fact is dangerous: an allergy or a medicine that comes out wrong.*
- *The hook: shared record systems such as Malaysia's rollout have to merge records that hospitals write differently. Two checked facts, each with a link.*

## What we built

*Owner: Daniel (T46b). About 3 sentences.*

- *In: three hospitals' records for one patient (a CSV table, a free-text letter, a brand-name sheet).*
- *Out: one merged record. Every fact shows its status, hospital, date and source quote, with a warning where something is unverified, in conflict or missing a dose.*
- *Link to the live app: (from Daniel's Vercel project).*

## What we added

*Owner: Daniel (T46b). Starts with the words "Our own idea".*

- *The three-hospital dataset built from Synthea patients.*
- *The checks and the six compile rules.*
- *The danger tiers and the test itself.*
- *One line: the language model is standard; what we built is everything around it.*

## How it works

*Owner: Daniel (T46b). About 5 sentences, plus the workflow diagram (T48).*

- *Data: 20 working patients and 80 held-out patients from the Synthea CSV sample, November 2021. Split fixed before anything was run.*
- *How the answer key was made: by script from Synthea's original record, with a hand spot-check.*
- *Which model, pinned version, temperature 0, and why it was chosen (T21, working patients only).*
- *The steps: extract, check, compile, store. Only extraction uses the model.*
- *The baseline: keyword matching with a stack-everything merge.*

## Results

*Owner: Abby (T46a). Filled from the held-out run only.*

- *The build-up table: baseline next to our tool, with critical errors, missed facts and false alarms in separate columns.*
- *Breakdown by age band and by sex.*
- *Drug-allergy patients reported as their own line (they were picked first in each group).*
- *Three failure examples: the record, the wrong output, and our best explanation.*

## Limits

*Owner: Abby (T46a). Short list.*

- *Synthea patients are artificial and US-style. No Malaysian hospital records were tested.*
- *We wrote the three hospital templates, so real records could produce more errors.*
- *One shared patient ID across hospitals. Matching patients without one is out of scope.*
- *The danger tiers are our own judgment, not validated by clinicians.*
- *19 of the 100 patients have no current medicine; they test the "no regular medicines recorded" case.*
- *Typed records only.*

## What we'd do next

*Owner: Daniel (T46b). About 3 bullets.*

- *Handwritten and scanned records.*
- *Matching the same patient across hospitals without a shared ID.*
- *Real records with permission.*

## Sources and credits

*Owner: Theo (T46c). Copied from `docs/credits.md` once every link is checked.*

## Rules checklist

*Owner: Theo (T46c). Tick each one against the final submission.*

- [ ] Team of one to three, and every listed member contributed.
- [ ] All work done inside the hackathon window.
- [ ] AI is central: the language model extracting records is the core.
- [ ] Only synthetic or public data. No real patient records.
- [ ] One track: AI + Health.
- [ ] The user and the moment they use it are named.
- [ ] This line appears exactly: "This project is a prototype and is not medical advice."
- [ ] Baseline score reported next to our tool's score.
- [ ] Results come from the held-out patients.
- [ ] Missed cases and false alarms reported separately.
- [ ] Results broken down by age band and by sex.
- [ ] At least one failure example with an explanation.
- [ ] "What we added" says: Our own idea.
- [ ] Credits list every dataset, model, tutorial and AI tool with a link.
- [ ] Code link is the public GitHub repo.
- [ ] No API key anywhere in the repo or the app.
- [ ] Every link opens in a private window without signing in.
- [ ] Team details correct: track, names, emails, schools.
