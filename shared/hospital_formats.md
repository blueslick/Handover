# Hospital formats v1.0 (T12)

Set by Daniel, Sat 14 Nov 2026. Abby and Theo confirm at the Sunday call (T10).
Code writes every record (`pipeline/data/templates/make_records.py`), never an AI.
All three hospital names are made up.

| Letter | Hospital | File | Format |
| --- | --- | --- | --- |
| A | Northfield General Hospital | `P014_A.csv` | CSV table, one row per fact, generic names |
| B | Riverside Community Hospital | `P014_B.txt` | Free-text clinic letter, one sentence per fact, generic names |
| C | Seri Bayu Medical Centre | `P014_C.txt` | Medication reconciliation sheet, **brand names**, short-hand frequencies |

Every record prints the patient ID (same ID at all three hospitals), name, date of birth and a visit date.

## Hospital A: the CSV header

UTF-8, commas, one header row. This header is the contract for Theo's upload screen.

```
MRN,PatientName,DOB,Sex,EncounterDate,RecordType,Description,Strength,Directions,Status,StatusDate,Reaction
```

| Column | What goes in it |
| --- | --- |
| MRN | Patient ID, e.g. `P014` |
| PatientName | `Last, First` (quoted, because of the comma) |
| DOB, EncounterDate, StatusDate | `YYYY-MM-DD` |
| Sex | `F` or `M` |
| RecordType | `ALLERGY`, `PROBLEM` (diagnosis), `MEDICATION`. `PROCEDURE` is reserved, not used yet |
| Description | Generic name or diagnosis, e.g. `Amlodipine`. Special rows: `No known allergies`, `No current medications` |
| Strength | `2.5 mg`, `44 mcg`. Blank when not written (combination tablets, creams, some injections) |
| Directions | `once daily`, `twice daily`, `three times daily`, `four times daily`, `at bedtime`, `once weekly`, `as needed`, `once`, or longer words such as `every 3 months` |
| Status | `Active` or `Discontinued` (medicines), `Active` (allergies, problems), blank on the special rows |
| StatusDate | Start date for active medicines, stop date for discontinued ones, onset for problems and allergies |
| Reaction | Allergies only, several joined with `; ` |

## Hospital B: free-text clinic letter

Letter header, then paragraphs: history, allergies, medicines, plan. Dates written as `4 June 2003`.
Frequencies in words (`once a day`, `twice a day`, `when needed`, `at night`). Stopped medicines say
`Her warfarin was stopped on 12 March 2021.` No allergies: `She has no known allergies.` No medicines:
`She takes no regular medicines.` Wording is picked at random from a few fixed openings, seeded by patient
ID, so the same patient always gets the same letter.

## Hospital C: brand-name layout

Boxed text sheet with `[ALLERGIES]`, `[PROBLEM LIST]`, `[CURRENT MEDICATIONS]`, `[DISCONTINUED]`.
Dates written `04-Jun-2003`. Medicines use the brand in `medicine_table.csv` (`Norvasc 2.5 mg OD`,
`Panadol 1 g PRN`); a medicine with no brand there is written by its generic name. Drug allergies use the
brand too where one exists (`Bactrim`, `Disprin`). Short-hand: `OD` once daily, `BD` twice daily, `TDS` three
times, `QID` four times, `ON` at night, `PRN` as needed, `STAT` once. Whole grams are written as grams
(`1000 mg` becomes `1 g`). No allergies: `NKA`. No medicines: `Nil regular medications`.

## The tables behind the templates

- `pipeline/data/templates/medicine_table.csv`: every one of the 143 medicine names that appears in the
  Synthea Nov 2021 data inside our 5-year window, plus three demo rows. For each: generic name (lowercase,
  as the answer key writes it), dose, frequency, Hospital C's brand, and other names (`acetaminophen`,
  `albuterol`). **This is the "full brand list" T15 builds `shared/brand_to_generic.csv` from**, so held-out
  patients are covered without anyone opening them.
- `pipeline/data/templates/allergy_table.csv`: the 21 allergy names in the data, cleaned.

## Choices made here that the team should know

- **Generic names.** Paracetamol and salbutamol (not acetaminophen and albuterol), to match the demo
  patient and Malaysian use. Every other medicine keeps Synthea's generic name with salts dropped.
- **Frequency is ours.** Synthea gives no frequency, so each medicine has one fixed, typical frequency in
  the table. Say so in the write-up.
- **Combination medicines have no dose** (e.g. Augmentin, Percocet, the pill packs). The answer-key dose is
  `null`, so the key flags `missing_dose` on them. Abby: skip the dose comparison when the key's dose is null.
- **Inactive allergies are left out** of all three records (none in the working set).
- Every template also returns the list of facts it wrote with the exact quote, so the answer-key script
  (T14) copies quotes instead of re-deriving them.

## Not decided here (T13)

Which facts each hospital mentions, each hospital's visit date, and which traps go in (a stop only one
hospital knows about, a dose change, an allergy one hospital missed). The templates only write what they
are given.

## Try it

```
python pipeline/data/templates/make_records.py --check-tables    # every medicine and allergy covered?
python pipeline/data/templates/make_records.py --preview P001    # all three formats for one working patient
```
