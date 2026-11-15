# Handover: write-up

Veritas AI International High School Hackathon 2026 · Track: AI + Health · Team: Daniel, Abby, Theo

This project is a prototype and is not medical advice.

The full write-up is the Google Doc **Handover write-up**:
https://docs.google.com/document/d/1lHzcvi0vvmdCBLFHJB3e1dCduw-LKhDw7dX_G8oRlHE/edit

That document is the one we submit and keep up to date. This file used to hold the first skeleton (T30); it was replaced on 15 Nov 2026 so nothing in the repo contradicts the final write-up (the skeleton still said 100 patients and "model TBD").

## In short

- **The user:** an emergency doctor whose patient has records at three other hospitals.
- **What it does:** Claude Sonnet 5.5 (`claude-sonnet-5-5`) reads each hospital's record; our code checks every fact against the record's own words, then six merge rules build one record. Every fact shows its hospital, date and exact source quote. When hospitals disagree, both are shown.
- **The test:** 180 synthetic patients (Synthea). 20 working patients for building; 160 held-out patients, 20 per age band and sex, used once after the tool was frozen. Missed facts and false alarms are counted separately.
- **Headline (160 held-out patients, 1,668 key facts):** the full tool missed 13 facts, raised 47 false alarms and showed all 38 disagreements. The keyword-search baseline missed 916, raised 1,312 false alarms and showed none. Of the 861 critical facts (allergies and current medicines), the tool missed 4.

Every number comes from the committed files in `outputs/results/heldout/`. The write-up has the full table, the age and sex breakdown, three failure examples and the limits.

## Credits

See `docs/credits.md`, which matches the Sources table in the write-up.
