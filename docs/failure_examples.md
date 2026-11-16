# Where the tool goes wrong: three examples

We tested the tool on 160 held-out patients it had never seen. It missed 13 of 1,668 facts and added 47 that weren't in the answer key. Nearly all of these mistakes come from **one cause**, and it shows up in three different ways.

**The cause.** Hospital B's notes are written as sentences, and they write a combination medicine (one product with two ingredients) as "X and Y". For example: *"He takes paracetamol and oxycodone when needed."* The tool sometimes reads that as two separate medicines instead of one product.

The examples below are from synthetic (made-up) patients. They are held-out patients P092 (example 1), P051 (example 2) and P066 (example 3), the same three named in the README. The cheaper model we compared, Claude Haiku 5.5, makes the same three mistakes.

---

## 1. A combination product goes missing

**What the record said.** Hospital B wrote a premixed insulin as *"insulin isophane and insulin regular"*. That is one product.

**What the tool showed.** Two separate insulins, and no entry for the premixed product. So the real product is missing from the list, and two extra entries appear in its place.

**Why.** The mistake happens at the first step, when the AI reads the note. The later steps can't fix it: they check names and merge records, but none of them asks "are these two names really one known product?"

**How often.** The tool split insulin in all 5 notes that wrote it this way. This type of split caused all 4 of the important facts the tool missed (an important fact is an allergy or a current medicine).

**How serious.** Low. Both insulin names still appear, along with the exact sentence from the note, so a doctor can see what was written.

## 2. A stopped medicine looks like it's still being taken

**What the record said.** One hospital recorded paracetamol as **stopped**. Later, Hospital B wrote *"He takes paracetamol and hydrocodone when needed"*, which is a combination painkiller, not plain paracetamol.

**What the tool showed.** Paracetamol as **current**. The split made a new "paracetamol" entry with a later date. The merge step correctly follows the rule that the newest information wins, so it overrode the stop. The stop is still visible in the medicine's history.

**Why.** The merge worked as designed. It was given a wrong fact by the reading step (the same split as example 1).

**How often.** It gave a wrong status for 5 of 160 patients. Two of these were planted "stopped at only one hospital" tests. The tool caught 72 of 74 of those tests. Keyword search caught none.

**How serious.** Low here, because paracetamol is part of the combination anyway. The same mistake on a riskier medicine would matter more.

You can see this mistake on sample patient **P012** in the app (Doctor screen): paracetamol shows as current, though one hospital stopped it.

## 3. An opioid is listed twice

**What the record said.** Hospitals A and C name a paracetamol and oxycodone combination painkiller clearly. Hospital B writes it as *"paracetamol and oxycodone"*.

**What the tool showed.** The combination (correct), **plus** oxycodone and paracetamol on their own. The opioid now appears twice.

**Why.** It's the same split again. Nothing goes missing, but the list gets extra entries.

**How often.** Split combinations added 38 extra entries across 20 of 160 patients. Paracetamol with hydrocodone was split in all 8 notes that wrote it this way.

**How serious.** Low. Nothing is missing and the source sentence is shown, but a longer list could lead a doctor to ask a question they didn't need to.

Sample patient **P012** in the app shows this one too: oxycodone appears on its own and inside the combination.

---

## What the three have in common

- **One cause explains most mistakes:** 9 of the 13 misses and 43 of the 47 extra entries.
- **The rest weren't really the tool's fault.** The other 4 misses and 4 extra entries come from 4 diagnosis names in our answer keys that have a double space in them. The tool wrote those names correctly. We don't edit answer keys after testing, so they stay counted against the tool.
- **The AI knows some combinations and not others.** It read familiar ones as one product (amoxicillin with clavulanate: 7 of 7; contraceptive pairs: 12 of 12). It split less familiar ones (paracetamol with hydrocodone: 8 of 8; insulin: 5 of 5; paracetamol with oxycodone: 5 of 6).
- **Our extra word-search check didn't catch these.** It pointed at only 1 of the 13 misses, because the medicine names do appear in the note.
- **It may partly be our test's fault.** "X and Y" is the wording of our own Hospital B template. Real hospital notes may write combinations differently.

**A possible fix (not built, because the tool was frozen before testing).** When the AI pulls two medicine names out of the same sentence, check them against our list of known combination medicines. If they match one, join them back into a single product. That would fix all three examples.

*This project is a prototype and is not medical advice.*
