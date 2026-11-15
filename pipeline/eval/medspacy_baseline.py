"""medSpaCy baseline (T42): a standard clinical rules-NLP extractor, kept only for comparison.

Row 2 of the build-up table: medSpaCy + stack. It sits between the plain keyword search
(row 1) and Claude (rows 4 to 7). It uses no AI and makes no model calls.

What it does, for each hospital record (whole text, one spaCy document):
- Sentences: one sentence per line, and a new sentence after a full stop. (medSpaCy's
  default PyRuSH splitter glued the brand-sheet header lines together, so it is replaced.)
- Target matcher: every drug name in shared/drug_list.csv and every brand name in
  shared/brand_to_generic.csv becomes an entity; a brand becomes its generic name. Two more
  phrase targets: "known allergies" and "regular/current medicines/medications".
- ConText (medSpaCy's NegEx-style modifiers, default rules plus three added ones):
  negated -> the fact is not kept, except the two phrase targets, which become
  "No known allergies" / "No regular medicines recorded" (status none_recorded) only when
  negated ("no known allergies", "Nil regular medications"). Added rules: "stopped" and
  "discontinued" mark a medicine as stopped; "nil" negates what follows. The brand sheet's
  "NKA" line is read as a fixed word (it is a whole statement, not a negated phrase).
- Hospital A (CSV table): one document per row, with commas spaced out so the fields split.
- Sectionizer: default clinical section titles plus the brand sheet's [ALLERGIES],
  [CURRENT MEDICATIONS], [DISCONTINUED] and [PROBLEM LIST]. A name under an allergies
  section is an allergy; a medicine under [DISCONTINUED] is stopped.
- Allergy or medicine otherwise follows the keyword baseline's rule (drug list kind column,
  or "allerg" on the line). Dose = number and unit written straight after the name.
No dose-change logic and no diagnoses (the drug list has none), same as the keyword baseline.
Then stack_merge.py keeps every fact from every hospital.

medspacy is optional and not in pipeline/requirements.txt (it brings spaCy). Install it
only to rerun this baseline:  .venv/bin/pip install medspacy==1.3.1

Usage (from the repo root, with the project venv and medspacy installed):
    .venv/bin/python pipeline/eval/medspacy_baseline.py D001
    .venv/bin/python pipeline/eval/medspacy_baseline.py --working      (P001 to P020)

Writes outputs/baseline_medspacy/<patient>.json (kind baseline_medspacy). Check it with
shared/validate.py. Only D001 and P001 to P020 are allowed; held-out and reserve IDs are
refused before any file is opened.
"""

import argparse
import sys
from pathlib import Path

from keyword_baseline import (
    ALLOWED, OUT as _KEYWORD_OUT, WORKING, classify_name, dose_after, load_kinds,
    load_names, record_files, visit_date,
)
from stack_merge import build_record, write_record

OUT = _KEYWORD_OUT.parent / "baseline_medspacy"

NO_ALLERGY = "NO_ALLERGY_PHRASE"
NO_MEDICINE = "NO_MEDICINE_PHRASE"
DRUG = "DRUG"
STOPPED = "STOPPED"


# Build the medSpaCy pipeline once: line sentencizer, target matcher, ConText, sectionizer.
def build_nlp(names):
    # medSpaCy logs a lot through loguru; keep only warnings.
    try:
        from loguru import logger
        logger.remove()
        logger.add(sys.stderr, level="WARNING")
    except ImportError:
        pass
    import medspacy
    from medspacy.context import ConTextRule
    from medspacy.section_detection import SectionRule
    from medspacy.target_matcher import TargetRule
    from spacy.language import Language

    @Language.component("line_sentencizer")
    def line_sentencizer(doc):
        for i, token in enumerate(doc):
            if i == 0:
                token.is_sent_start = True
                continue
            prev = doc[i - 1]
            token.is_sent_start = "\n" in prev.text or prev.text == "." or "\n" in token.text
        return doc

    nlp = medspacy.load(medspacy_enable=["medspacy_target_matcher", "medspacy_context"])
    nlp.add_pipe("line_sentencizer", first=True)
    # Only the brand sheet's own section titles: medSpaCy's default titles fire on ordinary
    # sentences such as "She has no known allergies." and would label later lines wrongly.
    nlp.add_pipe("medspacy_sectionizer", config={"rules": None})

    matcher = nlp.get_pipe("medspacy_target_matcher")
    rules = [TargetRule(written, DRUG) for written in sorted(names, key=len, reverse=True)]
    # Combination medicines are listed as "a / b"; letters write "a and b".
    for written in names:
        if " / " in written:
            rules.append(TargetRule(written.replace(" / ", " and "), DRUG))
    rules.append(TargetRule("known allergies", NO_ALLERGY))
    for phrase in ("regular medicines", "regular medications", "current medications", "current medicines"):
        rules.append(TargetRule(phrase, NO_MEDICINE))
    matcher.add(rules)

    context = nlp.get_pipe("medspacy_context")
    context.add([
        ConTextRule("stopped", STOPPED, direction="BIDIRECTIONAL"),
        ConTextRule("discontinued", STOPPED, direction="BIDIRECTIONAL"),
        ConTextRule("nil", "NEGATED_EXISTENCE", direction="FORWARD"),
    ])

    sectionizer = nlp.get_pipe("medspacy_sectionizer")
    sectionizer.add([
        SectionRule("[ALLERGIES]", "allergies"),
        SectionRule("[CURRENT MEDICATIONS]", "medications"),
        SectionRule("[DISCONTINUED]", "discontinued"),
        SectionRule("[PROBLEM LIST]", "problem_list"),
    ])
    return nlp


# The full line of the record an entity sits on, used as the quote.
def line_of(text, start_char):
    begin = text.rfind("\n", 0, start_char) + 1
    end = text.find("\n", start_char)
    return text[begin:end if end != -1 else len(text)].strip()


def is_stopped(ent):
    return any(mod.category == STOPPED for mod in ent._.modifiers)


# Run medSpaCy on one hospital record and return facts in the extracted shape.
def extract_record(path, hospital, names, kinds, nlp):
    text = path.read_text(encoding="utf-8")
    date = visit_date(path, hospital, text)
    if hospital == "A":
        # The CSV table: one document per row, commas spaced out so the tokenizer splits
        # the fields. The quote is the row exactly as written.
        rows = [line for line in text.splitlines()[1:] if line.strip()]
        docs = [(row, nlp(row.replace(",", " , "))) for row in rows]
    else:
        docs = [(None, nlp(text))]
    facts = []
    seen_none = set()
    for row, doc in docs:
        facts.extend(entity_facts(doc, row, text, names, kinds, date, seen_none))

    # The brand sheet writes "NKA" for no known allergies. NKA is a whole statement, not a
    # negated phrase, so it is read here as a fixed word rather than through ConText.
    if "allergy" not in seen_none:
        for raw in text.splitlines():
            if raw.strip().lstrip("- ").strip().lower() == "nka":
                facts.append(none_fact("allergy", "NKA", raw.strip(), date))
                break
    return facts


# Turn the entities medSpaCy found in one document into facts.
# row is the CSV row as written (Hospital A), or None when doc is the whole record.
def entity_facts(doc, row, text, names, kinds, date, seen_none):
    facts = []
    for ent in doc.ents:
        quote = row if row is not None else line_of(text, ent.start_char)
        section = ent._.section_category or ""

        if ent.label_ in (NO_ALLERGY, NO_MEDICINE):
            if not ent._.is_negated:
                continue
            fact_type = "allergy" if ent.label_ == NO_ALLERGY else "medicine"
            if fact_type in seen_none:
                continue
            seen_none.add(fact_type)
            facts.append(none_fact(fact_type, ent.text, quote, date))
            continue

        if ent._.is_negated:
            continue
        written = ent.text
        generic = names.get(written.lower()) or names[written.lower().replace(" and ", " / ")]
        if section == "allergies":
            fact_type = "allergy"
        else:
            fact_type = classify_name(generic, quote, kinds)
        if fact_type == "allergy":
            status, dose = "current", None
        else:
            stopped = is_stopped(ent) or section == "discontinued"
            status = "stopped" if stopped else "current"
            dose = dose_after(quote, quote.lower().find(written.lower()) + len(written))
        flags = ["missing_dose"] if fact_type == "medicine" and status == "current" and dose is None else []
        facts.append({
            "type": fact_type, "name": generic, "name_as_written": written,
            "dose": dose, "frequency": None, "reaction": None, "status": status,
            "date": date, "quote": quote, "flags": flags,
        })
    return facts


def none_fact(fact_type, written, quote, date):
    return {
        "type": fact_type, "name": None, "name_as_written": written,
        "dose": None, "frequency": None, "reaction": None, "status": "none_recorded",
        "date": date, "quote": quote, "flags": [],
    }


def run_patient(patient_id, names, kinds, nlp):
    files = record_files(patient_id)
    if len(files) != 3:
        raise SystemExit(f"{patient_id}: expected 3 hospital records, found {len(files)}")
    extractions = []
    for path in files:
        hospital = path.stem.split("_")[-1]
        extractions.append({
            "patient_id": patient_id, "hospital": hospital, "source_file": path.name,
            "facts": extract_record(path, hospital, names, kinds, nlp),
        })
    return build_record("baseline_medspacy", patient_id, None, extractions)


def main():
    ap = argparse.ArgumentParser(description="medSpaCy baseline (T42). See the top of this file.")
    ap.add_argument("patients", nargs="*", help="e.g. D001 P001")
    ap.add_argument("--working", action="store_true", help="run P001 to P020")
    ap.add_argument("--out-dir", default=str(OUT), help="where to write (default outputs/baseline_medspacy)")
    args = ap.parse_args()

    ids = list(args.patients) + (WORKING if args.working else [])
    if not ids:
        ap.error("give patient IDs, or --working")
    for pid in ids:
        if pid not in ALLOWED:
            ap.error(f"{pid} is not allowed: only D001 and P001-P020 (held-out and reserve IDs are refused)")

    names = load_names()
    kinds = load_kinds()
    nlp = build_nlp(names)
    for pid in dict.fromkeys(ids):
        record = run_patient(pid, names, kinds, nlp)
        out = Path(args.out_dir) / f"{pid}.json"
        write_record(record, out)
        print(f"{pid}: {len(record['facts'])} facts -> {out}")


if __name__ == "__main__":
    main()
