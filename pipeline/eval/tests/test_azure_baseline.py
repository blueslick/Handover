"""Tests for azure_baseline.py (T76). Run from the repo root: .venv/bin/python -m pytest pipeline/eval/tests

Every test uses saved fake Azure replies written here. None of them uses the network: call_azure
is replaced by a function that fails the test if it is ever reached.
"""

import json
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL))

import azure_baseline as ab  # noqa: E402

NAMES = ab.load_names()
KINDS = ab.load_kinds()


# A fake Azure entity: the given words found at their first place in text.
def ent(text, words, category="MedicationName", **assertion):
    e = {"text": words, "category": category, "offset": text.index(words), "length": len(words)}
    if assertion:
        e["assertion"] = assertion
    return e


def rel(kind, *members):
    return {"relationType": kind,
            "entities": [{"ref": f"#/results/documents/0/entities/{i}", "role": r} for r, i in members]}


def facts_for(text, entities, relations=(), rows=None):
    doc = {"id": "T001_B", "entities": entities, "relations": list(relations)}
    facts, unnamed = ab.translate(doc, text, rows, "2021-07-14", NAMES, KINDS)
    return facts, unnamed


def one(text, entity, relations=()):
    facts, _ = facts_for(text, [entity], relations)
    return facts


# Rule 2: a brand becomes its generic name; a name not in our lists gives no fact and is counted.
def test_brand_becomes_generic_and_unknown_names_are_counted():
    text = "She takes Panadol 1 g and Zorblex 5 mg."
    facts, unnamed = facts_for(text, [ent(text, "Panadol"), ent(text, "Zorblex")])
    assert [(f["name"], f["status"]) for f in facts] == [("paracetamol", "current")]
    assert unnamed == 1


def test_only_medication_and_allergen_items_count():
    text = "She has hypertension and takes amlodipine."
    facts, unnamed = facts_for(text, [ent(text, "hypertension", "Diagnosis"), ent(text, "amlodipine")])
    assert [f["name"] for f in facts] == ["amlodipine"]
    assert unnamed == 0


# Rule 3: Allergen is an allergy; a medicine name on an "allerg" line is an allergy.
def test_allergy_or_medicine():
    text = "Allergic to penicillin."
    assert one(text, ent(text, "penicillin", "Allergen"))[0]["type"] == "allergy"
    assert one(text, ent(text, "penicillin"))[0]["type"] == "allergy"
    text2 = "She takes lisinopril 10 mg."
    assert one(text2, ent(text2, "lisinopril"))[0]["type"] == "medicine"


# Rules 4, 5, 8: someone else, negated, conditional -> no fact.
@pytest.mark.parametrize("assertion", [
    {"association": "other"}, {"certainty": "negative"}, {"certainty": "negativePossible"},
    {"conditionality": "conditional"},
])
def test_no_fact(assertion):
    text = "Her mother takes metformin."
    assert one(text, ent(text, "metformin", **assertion)) == []


# Rule 6: possible allergy -> suspected; possible medicine stays current.
def test_possible():
    text = "Possible allergy to penicillin.\nMaybe metformin."
    assert one(text, ent(text, "penicillin", "Allergen", certainty="positivePossible"))[0]["status"] == "suspected"
    assert one(text, ent(text, "metformin", certainty="neutralPossible"))[0]["status"] == "current"


# Rule 7: past, or a Course link with a stop word -> stopped. Rule 8: future / hypothetical -> planned.
def test_stopped_and_planned():
    text = "Warfarin was stopped. Start metformin."
    assert one(text, ent(text, "Warfarin", temporality="past"))[0]["status"] == "stopped"
    course = [ent(text, "Warfarin"), ent(text, "stopped", "Course")]
    facts, _ = facts_for(text, course, [rel("CourseOfMedication", ("Medication", 0), ("Course", 1))])
    assert facts[0]["status"] == "stopped"
    assert one(text, ent(text, "metformin", temporality="future"))[0]["status"] == "planned"
    assert one(text, ent(text, "metformin", conditionality="hypothetical"))[0]["status"] == "planned"


def test_course_without_stop_word_stays_current():
    text = "Warfarin was increased."
    course = [ent(text, "Warfarin"), ent(text, "increased", "Course")]
    facts, _ = facts_for(text, course, [rel("CourseOfMedication", ("Medication", 0), ("Course", 1))])
    assert facts[0]["status"] == "current"


# Rule 10: dose only from the dosage link; none -> missing_dose on a current medicine.
def test_dose_only_from_link():
    text = "She takes amlodipine 5 mg once a day."
    linked = [ent(text, "amlodipine"), ent(text, "5 mg", "Dosage")]
    facts, _ = facts_for(text, linked, [rel("DosageOfMedication", ("Dosage", 1), ("Medication", 0))])
    assert (facts[0]["dose"], facts[0]["flags"], facts[0]["frequency"]) == ("5 mg", [], None)
    bare = one(text, ent(text, "amlodipine"))[0]
    assert (bare["dose"], bare["flags"]) == (None, ["missing_dose"])


# Rule 12 and Hospital A: one document, one row per line, commas spaced; the quote is the row as written.
def test_hospital_a_rows_and_quotes(tmp_path):
    path = tmp_path / "T001_A.csv"
    path.write_text("MRN,EncounterDate,RecordType,Description,Strength\n"
                    "T001,2021-07-14,ALLERGY,Penicillin,\n"
                    "T001,2021-07-14,MEDICATION,Metformin,500 mg\n", encoding="utf-8")
    text, rows = ab.document_text(path, "A")
    assert text.splitlines()[1] == "T001 , 2021-07-14 , MEDICATION , Metformin , 500 mg"
    facts, _ = facts_for(text, [ent(text, "Penicillin"), ent(text, "Metformin")], rows=rows)
    assert [(f["type"], f["quote"]) for f in facts] == [
        ("allergy", "T001,2021-07-14,ALLERGY,Penicillin,"),
        ("medicine", "T001,2021-07-14,MEDICATION,Metformin,500 mg"),
    ]


def test_combination_written_with_and():
    text = "She takes levonorgestrel and ethinyl estradiol."
    fact = one(text, ent(text, "levonorgestrel and ethinyl estradiol"))[0]
    assert fact["name"] == "levonorgestrel / ethinyl estradiol"


# Saved replies: a document already answered is never sent again.
def fake_reply(doc_ids, version="2023-04-15"):
    return {"status": "succeeded", "tasks": {"items": [{"results": {
        "modelVersion": version, "errors": [],
        "documents": [{"id": i, "entities": [], "relations": []} for i in doc_ids]}}]}}


def test_saved_replies_are_not_sent_again(tmp_path, monkeypatch):
    docs = [{"id": "T001_B", "text": "x"}, {"id": "T001_C", "text": "y"}]
    replies = tmp_path / "replies"
    replies.mkdir()
    request = {"analysisInput": {"documents": docs}}
    (replies / "batch_0001.json").write_text(
        json.dumps({"request": request, "reply": fake_reply(["T001_B", "T001_C"])}), encoding="utf-8")
    saved = ab.load_saved(replies)
    assert saved["T001_B"][1] == "2023-04-15"
    assert saved["T001_B"][2] == ab.text_hash("x")

    def no_network(*_a, **_k):
        raise AssertionError("Azure must not be called")
    monkeypatch.setattr(ab, "call_azure", no_network)
    assert ab.fetch_missing(docs, saved, replies, "k", "e") == 0


def test_new_reply_is_saved_before_use(tmp_path, monkeypatch):
    docs = [{"id": "T002_B", "text": "z"}]
    monkeypatch.setattr(ab, "call_azure", lambda batch, k, e: (
        {"analysisInput": {"documents": batch}}, fake_reply([d["id"] for d in batch]), 3))
    saved = {}
    assert ab.fetch_missing(docs, saved, tmp_path, "k", "e") == 3
    assert json.loads((tmp_path / "batch_0001.json").read_text(encoding="utf-8"))["reply"]["status"] == "succeeded"
    assert "T002_B" in saved


def test_text_records():
    assert [ab.text_records(n) for n in (1, 1000, 1001, 2500)] == [1, 1, 2, 3]
