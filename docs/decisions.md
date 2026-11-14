# Decisions

One dated line per fix or decision.

- 2026-11-14: Dataset is the Synthea CSV sample, Nov 2021 (1,163 patients), not the "latest" sample (111 patients, only 7 drug allergies). (T04)
- 2026-11-14: Four age bands (0-19, 20-44, 45-64, 65+) x 2 sexes, 10 held-out each: 80 held-out + 20 working = 100 patients, up from 80. Ages taken on 18 Nov 2021. (T11)
- 2026-11-14: Pool is patients alive on 18 Nov 2021 with at least one current medicine. Up to 3 drug-allergy patients per held-out group are taken first; the write-up states this and reports allergy results as their own line. (T11)
- 2026-11-14: An 80-patient reserve batch (heldout_ext_ids.txt) is picked by the same rule. It can be added only if the decision is made before any held-out result is seen. (T11)
- 2026-11-14: Split made with select_patients.py, seed 20261114. (T11)
- 2026-11-14 (T01 T02, Daniel): Added the shared record format v1.0, the folder skeleton, `.gitignore` (merged with T03's), and `pipeline/requirements.txt` (`jsonschema>=4.20` added beside the existing pins) from the handover pack. Added a "Team rules" section to CLAUDE.md, leaving out two pasted lines that conflict with CLAUDE.md: the `pipeline/data/` handover day (Sunday vs Saturday night) and the per-person owners of `outputs/` subfolders. Those two need a team decision.
- 2026-11-14 (T01 T02, Daniel): Settled the two open items. `pipeline/data/` passes from Daniel to Abby when Daniel posts the hand-over in the team chat (target Saturday night). `outputs/published/` has one writer, Daniel, because it holds the frozen run. Other `outputs/` folders keep the rule "whoever ran the script owns the file". Added to CLAUDE.md under Team rules. `pipeline/data/README.md` already existed, so it was not recreated.
- 2026-11-14 (T03): Plan, plan v2 and task breakdown added to docs/; Handover plan wins over plan v2.
- 2026-11-14 (T03): docs/: plan v2 replaced with the v2 summary; task breakdown replaced with the newer version.
- 2026-11-14: The pipeline needs Python 3.11+ (pandas 3.0.5 does not install on 3.9). Daniel uses Homebrew python@3.12 in .venv. (T11)
- 2026-11-14 (T01 T02 T11, Daniel): Brought shared/ and CLAUDE.md in line with the T11 split: 100 scored patients (P001-P020 working, P021-P100 held-out) and reserve R001-R080; schemas now accept R IDs. Task breakdown restored to the version sent to the team (only wording differs).
- 2026-11-14 (T11, Daniel): Added an update note to the top of docs/Handover_Pipeline_and_Frontend_Plan.md pointing to the 100-patient split, so sessions don't stop on the 60 vs 80 mismatch.
