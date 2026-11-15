# Record format v1.0 (T01)

Set by Daniel, Sat 14 Nov 2026. Abby and Theo confirm at the Sunday 15-minute call (T10).
Changes after that go through the team chat first, because `shared/` has one writer at a time.

The machine-readable versions are the source of truth:

- `shared/fixed_lists.json`: every fixed list, plus the words the app shows for each label
- `shared/schema/extracted.schema.json`: facts from **one** hospital record (sections 4 and 5)
- `shared/schema/compiled.schema.json`: one merged record per patient (section 7). Answer keys and both baselines use this shape too, so scoring compares like with like
- `shared/validate.py`: run it on any file before you commit it (`pip install jsonschema`)
- `shared/examples/`: one valid file of each shape

## Two shapes

The plan's draft had one shape. It needs two, because a fact read from one record has no history yet, and a compiled fact can come from several hospitals (compile rule 1).

| | Extracted fact | Compiled fact |
| --- | --- | --- |
| Comes from | One hospital record | All records for one patient |
| Written by | Section 4 (model), cleaned by section 5 | Section 7, the answer-key script, the baselines |
| Has `hospital` per fact | No, it's on the file | Yes, the latest source |
| Has `sources`, `history`, `fact_id`, `conflict_group` | No | Yes |

## Fields on a compiled fact

| Field | Rule |
| --- | --- |
| `fact_id` | `<patient>-F<nn>`, e.g. `P014-F03`. Unique in the file. For the app and cross-references only; scoring matches on `type` + `name`, never on `fact_id` |
| `patient_id` | `P001` to `P020` working, `P021` to `P100` held-out, `R001` to `R080` reserve, `D001` the demo patient. `pipeline/data/patients.csv` is the source of truth for the split |
| `type` | `allergy`, `medicine`, `diagnosis`, `operation` |
| `name` | Generic name, lowercase (`paracetamol`, not `Panadol`). `null` only when the status is `none_recorded`, or when the name isn't in the brand table (then flag `unknown_name` and keep the original in `name_as_written`) |
| `name_as_written` | Exactly as the source wrote it. Lets the card show "Panadol (paracetamol)" |
| `dose` | Medicines only. `"<number> <unit>"`, units from the fixed list: `"3 mg"`, `"1000 mg"`, `"0.5 mg"`. Convert `1 g` to `1000 mg`. `null` if not written |
| `frequency` | Medicines only. One of: once, daily, twice_daily, three_times_daily, four_times_daily, at_night, weekly, as_needed, other. `BD` = twice_daily, `PRN` = as_needed |
| `reaction` | Allergies only. Free text as written (`"rash"`), or `null` |
| `status` | See the table below. Only some statuses are allowed for each type |
| `hospital`, `date`, `quote` | The latest source for the current value. `date` is ISO `YYYY-MM-DD`: the date the record gives for the fact, otherwise the record's visit date (so every template must print a visit date) |
| `quote` | Verbatim substring of the source record. The Check step tests this by string match, so no tidying |
| `sources` | Every hospital record that states the **current** value (rule 1). At least one |
| `history` | Earlier **different** values, oldest first (rules 2 and 3). Empty if nothing changed |
| `flags` | From the fixed list. `dose_changed` needs a history entry. `conflict` needs a `conflict_group` |
| `conflict_group` | `<patient>-C<n>`. Every fact on each side of a conflict gets the same group, so the app can show them side by side (rules 5 and 6). `null` otherwise |

## Statuses by type

| Type | Allowed statuses | App shows |
| --- | --- | --- |
| allergy | current, suspected, none_recorded, side_effect | Allergy / Suspected allergy / No known allergies / Side effect, not an allergy |
| medicine | current, stopped, planned, none_recorded | Current / Stopped / Planned / No regular medicines recorded |
| diagnosis | current, stopped, suspected, family_history | Current / Resolved / Suspected / Family history |
| operation | current, planned | Done / Planned |

The seven labels stay exactly as the plan listed them. Rather than add "resolved" or "done", the app maps a label to words per type (`display_labels` in `fixed_lists.json`).

## How the compile rules show up in the format

1. **Same drug, one fact.** One compiled fact, several entries in `sources`.
2. **Explicit stop.** `status: "stopped"`. The earlier current entry moves to `history`.
3. **Dose change.** New dose on the fact, old dose in `history`, flag `dose_changed`.
4. **Silence.** Nothing changes. `hospital` and `date` keep showing where it was last recorded.
5. **Allergy vs "no known allergies".** Two facts, same `conflict_group`, both flagged `conflict`. The no-allergy side is `type: allergy, name: null, status: none_recorded`.
6. **Any other disagreement on a critical fact.** Same as 5: both sides kept, grouped, flagged.

## File wrappers

- **Extracted** (`outputs/extracted/<run_id>/P001_A.json`): `patient_id`, `hospital`, `source_file`, `run_id`, `model`, `prompt_version`, `temperature` (`null`: Claude 5.5 models refuse the setting, T56), `settings` (optional, the model settings used, in words), `attempt` (1, or 2 for the one retry), `usage` (input and output tokens from the API response), `facts`.
- **Compiled** (`outputs/compiled/<run_id>/P001.json`, also answer keys and baselines): `kind` (compiled, answer_key, baseline_keyword, baseline_medspacy, baseline_rules_row), `patient_id`, `run_id` (`null` for answer keys and the hand-written sample), `built_from` (the record file names), `facts`.

## Added beyond the plan's draft, so please check these on Sunday

- Two shapes instead of one, plus `sources`, `fact_id`, `conflict_group`, `name_as_written` and `reaction`.
- Fixed lists for dose units and frequency. Scoring can't compare free-text doses fairly.
- `D001` as the demo patient's ID, so it can't slip into a scored run by accident.
- Statuses allowed per type, and the per-type words the app shows.
