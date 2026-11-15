T38 (Abby): three failure examples from the held-out run (row 7, full tool, Sonnet 5.5), chosen after scoring. Quotes from synthetic records.

# Failure examples

One weakness shows up three ways: Hospital B's note writes a combination medicine as "X and Y", and the tool reads it as two medicines. (1) a product goes missing, (2) a stop gets lost, (3) an opioid is listed twice. All three are low harm: the doctor still sees both drug names and the source quote.

## A. For the How we tested tab (paste-ready)

Goes in Theo's `app/data/results.json`, field `failure_examples`. No held-out patient IDs.

```json
[
  {
    "title": "A premixed insulin is shown as two separate insulins",
    "explanation": "A held-out patient's Hospital B note said: \"She is on insulin isophane and insulin regular twice a day.\" That is one premixed product, so the tool should have shown one insulin. It listed two separate insulins and no combined entry, so the product went missing. The wrong step was reading the note: the model took \"and\" to mean two medicines. This lost a combination product for 3 of 160 held-out patients. Names and quote still showed, so low harm. You can see the same mistake on sample patient P012."
  },
  {
    "title": "A stopped medicine looks current again after the same split",
    "explanation": "Hospital A recorded paracetamol as stopped. A later Hospital B note said: \"He takes paracetamol and hydrocodone when needed.\" The tool split that into a newer \"paracetamol, current\" entry, which overrode the stop; it should have shown paracetamol stopped. The stop is still visible in the history. This was one of the 2 planted \"stopped at one hospital\" tests the tool missed, because of the same split. A status came out wrong this way for 5 of 160 held-out patients. Low harm: paracetamol is in the combination anyway."
  },
  {
    "title": "An opioid is listed twice, once alone and once in a combination",
    "explanation": "A held-out patient's Hospital B note said: \"He takes paracetamol and oxycodone when needed.\" Hospitals A and C name the combination painkiller clearly, and the tool got that right. It also listed oxycodone as a separate current medicine, so the opioid appears twice; it should have shown only the combination. The wrong step was reading Hospital B's note. Extra entries like this appeared for 20 of 160 held-out patients. Low harm: nothing is missing and the quote is shown, but the list is longer and could prompt a needless question."
  }
]
```

## B. For the write-up (T46a, "Failure examples")

### Example 1. P092: a combination product goes missing

**The record.** Hospital A has no insulin. Hospital B (16 Nov 2021): "She is on insulin isophane and insulin regular twice a day." The answer key has one premixed product, `insulin isophane / insulin regular`.

**The wrong output.** The tool shows two separate current insulins and no combined entry: 1 missed, 2 false alarms. The model wrote them at the first step (Extract); later steps passed them on. Haiku does the same.

**Our best explanation.** The sentence reads like two medicines. The model read "amoxicillin and clavulanate" in the same note as one, probably because that pair is its prompt's example (our guess).

**Fix (not done, tool frozen).** Merge two facts from one quote when their names match a combination in `shared/drug_list.csv`.

**Pattern.** Insulin was split in 5 of 5 notes; 3 patients lost a product.

### Example 2. P051: a stop gets lost

**The record.** Hospital C (25 Oct 2020) lists Panadol 325 mg as current. Hospital A: `Paracetamol,325 mg,as needed,Discontinued,2020-10-29`. Hospital B (14 Nov 2021): "He takes paracetamol and hydrocodone when needed." The key has paracetamol stopped. This is a planted "stopped at one hospital" test.

**The wrong output.** Extract split B's sentence, and Compile's rule "the latest dated value wins" let that new paracetamol override A's stop. It shows current; the stop sits in its history. 1 wrong status, trap not caught. Haiku does the same.

**Our best explanation.** The merge worked as designed; the split invented the newer paracetamol.

**Fix (not done, tool frozen).** The same combination-merge rule as example 1.

**Pattern.** 5 patients (P051, P076, R003, R010, R014); P051 and R014 are the 2 traps missed.

### Example 3. P066: an opioid is listed twice

**The record.** Hospital A lists `Paracetamol / hydrocodone` and `Paracetamol / oxycodone`; Hospital C lists Vicodin and Percocet. Hospital B (17 Sep 2021): "He takes paracetamol and oxycodone when needed." (and a similar hydrocodone sentence). The key has the two combinations only.

**The wrong output.** Both combinations appear, plus `oxycodone`, `hydrocodone` and `paracetamol` as separate current medicines from B: 3 false alarms. Haiku does the same.

**Our best explanation.** Same as example 1: "X and Y" is read as two medicines, and no later step asks whether the pair is a known combination.

**Fix (not done, tool frozen).** The same merge rule; the extras would join the combinations.

**Pattern.** 38 extra entries across 20 patients; paracetamol / hydrocodone was split in 8 of 8 notes.

### What the three have in common

All three come from one cause: Hospital B writes a combination as "X and Y", our test template's wording (Hospitals A and C name products clearly); real notes may differ. The model reads familiar combinations as one product (amoxicillin / clavulanate 7 of 7, contraceptive pairs 12 of 12) but splits less familiar ones (paracetamol / hydrocodone 8 of 8, insulin 5 of 5, paracetamol / oxycodone 5 of 6); Haiku too. This explains 9 of the tool's 13 misses and 43 of its 47 false alarms. The other 4 + 4 are a double space in 4 answer-key diagnosis names (the tool was right), unchanged (keys are never edited after the freeze). The omission check caught 1 of 13.
