"""Daniel's own checks for the compile step (T23). Abby's rule tests (T17) live in
pipeline/eval/tests/ and are the ones that count; these only make sure each rule
works before hers arrive, and cover messy model output the answer key never sees.

Run: python pipeline/tool/test_compile.py
Uses made-up facts under the demo ID D001; no real or held-out data.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compile import compile_patient, validate  # noqa: E402


def fact(type_, name, status="current", dose=None, freq=None, date="2021-01-01",
         quote=None, written=None, reaction=None, flags=None):
    return {"type": type_, "name": name, "name_as_written": written or name, "dose": dose,
            "frequency": freq, "reaction": reaction, "status": status, "date": date,
            "quote": quote or f"{written or name} {status}", "flags": flags or []}


def rec(hospital, *facts):
    return {"hospital": hospital, "source_file": f"D001_{hospital}.{'csv' if hospital == 'A' else 'txt'}",
            "facts": list(facts)}


def run(*records):
    out = compile_patient("D001", list(records))
    problems = validate(out)
    assert not problems, problems
    return out["facts"]


def named(facts, name):
    return [f for f in facts if f["name"] == name]


class Rule1SameDrugOneFact(unittest.TestCase):
    def test_brand_and_generic_merge(self):
        facts = run(rec("A", fact("medicine", "paracetamol", dose="1000 mg", freq="as_needed")),
                    rec("C", fact("medicine", None, dose="1 g", freq="as_needed", written="Panadol",
                                  date="2021-03-01")))
        [p] = named(facts, "paracetamol")
        self.assertEqual([s["hospital"] for s in p["sources"]], ["A", "C"])
        self.assertEqual(p["dose"], "1000 mg")
        self.assertEqual(p["history"], [])

    def test_brand_left_in_name_field(self):
        facts = run(rec("C", fact("medicine", "Glucophage", dose="500 mg")))
        self.assertEqual(facts[0]["name"], "metformin")

    def test_unknown_name_kept_and_flagged(self):
        facts = run(rec("C", fact("medicine", None, dose="5 mg", written="Zzyxol")),
                    rec("B", fact("medicine", None, dose="5 mg", written="zzyxol", date="2021-02-01")))
        self.assertEqual(len(facts), 1)
        self.assertIsNone(facts[0]["name"])
        self.assertIn("unknown_name", facts[0]["flags"])


class Rule2ExplicitStop(unittest.TestCase):
    def test_later_stop_wins_and_keeps_history(self):
        facts = run(rec("A", fact("medicine", "warfarin", dose="5 mg", date="2021-01-01")),
                    rec("B", fact("medicine", "warfarin", status="stopped", date="2021-06-20")))
        [w] = facts
        self.assertEqual(w["status"], "stopped")
        self.assertEqual(w["dose"], "5 mg")                     # last dose taken
        self.assertEqual(w["history"][0]["status"], "current")
        self.assertNotIn("conflict", w["flags"])


class Rule3DoseChange(unittest.TestCase):
    def test_later_dose_replaces_earlier(self):
        facts = run(rec("A", fact("medicine", "metformin", dose="500 mg", date="2021-03-02")),
                    rec("B", fact("medicine", "metformin", dose="1000 mg", date="2021-07-14")))
        [m] = facts
        self.assertEqual(m["dose"], "1000 mg")
        self.assertEqual(m["status"], "current")
        self.assertIn("dose_changed", m["flags"])
        self.assertEqual(m["history"][0]["dose"], "500 mg")

    def test_same_dose_written_as_grams_is_not_a_change(self):
        facts = run(rec("B", fact("medicine", "metformin", dose="1000 mg", date="2021-07-14")),
                    rec("C", fact("medicine", "metformin", dose="1 g", date="2021-10-05")))
        self.assertNotIn("dose_changed", facts[0]["flags"])
        self.assertEqual(len(facts[0]["sources"]), 2)


class Rule4SilenceIsNotAStop(unittest.TestCase):
    def test_drug_missing_from_latest_record_stays_current(self):
        facts = run(rec("A", fact("medicine", "lisinopril", dose="10 mg", date="2021-01-01")),
                    rec("C", fact("medicine", "metformin", dose="500 mg", date="2021-10-01")))
        [l] = named(facts, "lisinopril")
        self.assertEqual(l["status"], "current")
        self.assertEqual((l["hospital"], l["date"]), ("A", "2021-01-01"))


class Rule5AllergiesNeverRemoved(unittest.TestCase):
    def test_nka_vs_allergy_is_a_conflict(self):
        facts = run(rec("A", fact("allergy", "penicillin", date="2021-03-02")),
                    rec("B", fact("allergy", None, status="none_recorded", date="2021-07-14")),
                    rec("C", fact("allergy", None, status="none_recorded", date="2021-10-05")))
        self.assertEqual(len(facts), 2)
        groups = {f["conflict_group"] for f in facts}
        self.assertEqual(len(groups), 1)
        self.assertIsNotNone(groups.pop())
        [none] = [f for f in facts if f["status"] == "none_recorded"]
        self.assertEqual(len(none["sources"]), 2)

    def test_side_effect_does_not_clash_with_nka(self):
        facts = run(rec("A", fact("allergy", "codeine", status="side_effect")),
                    rec("B", fact("allergy", None, status="none_recorded", date="2021-02-01")))
        self.assertTrue(all(f["conflict_group"] is None for f in facts))


class Rule6OtherDisagreements(unittest.TestCase):
    def test_later_record_cannot_downgrade_an_allergy(self):
        facts = run(rec("A", fact("allergy", "penicillin", date="2021-01-01")),
                    rec("B", fact("allergy", "penicillin", status="side_effect", date="2021-05-01")))
        self.assertEqual(len(facts), 2)
        self.assertEqual(len({f["conflict_group"] for f in facts}), 1)

    def test_different_reactions_conflict_but_punctuation_does_not(self):
        same = run(rec("A", fact("allergy", "fish", reaction="hives; rash")),
                   rec("B", fact("allergy", "fish", reaction="hives and rash", date="2021-02-01")))
        self.assertEqual(len(same), 1)
        diff = run(rec("A", fact("allergy", "fish", reaction="hives")),
                   rec("B", fact("allergy", "fish", reaction="swelling", date="2021-02-01")))
        self.assertEqual(len(diff), 2)

    def test_same_date_different_doses_conflict(self):
        facts = run(rec("A", fact("medicine", "warfarin", dose="5 mg", date="2021-05-01")),
                    rec("B", fact("medicine", "warfarin", dose="3 mg", date="2021-05-01")))
        self.assertEqual(len(facts), 2)
        self.assertTrue(all("conflict" in f["flags"] for f in facts))

    def test_no_regular_medicines_vs_earlier_current_medicine(self):
        facts = run(rec("A", fact("medicine", "lisinopril", dose="10 mg", date="2021-01-01")),
                    rec("B", fact("medicine", None, status="none_recorded", date="2021-06-01")),
                    rec("C", fact("medicine", "metformin", dose="500 mg", date="2021-09-01")))
        [l] = named(facts, "lisinopril")
        [m] = named(facts, "metformin")
        self.assertIsNotNone(l["conflict_group"])
        self.assertIsNone(m["conflict_group"])   # started after: a new start, not a clash


class MessyInput(unittest.TestCase):
    def test_missing_date_takes_the_records_latest_date(self):
        facts = run(rec("A", fact("medicine", "warfarin", dose="5 mg", date="2021-01-01")),
                    rec("B", fact("medicine", "warfarin", status="stopped", date=None),
                        fact("diagnosis", "atrial fibrillation", date="2021-06-20")))
        [w] = named(facts, "warfarin")
        self.assertEqual((w["status"], w["date"]), ("stopped", "2021-06-20"))

    def test_current_medicine_without_dose_is_flagged(self):
        facts = run(rec("B", fact("medicine", "metformin", dose=None)))
        self.assertIn("missing_dose", facts[0]["flags"])

    def test_check_step_flags_are_kept(self):
        facts = run(rec("B", fact("medicine", "metformin", dose="500 mg", flags=["unverified"])))
        self.assertIn("unverified", facts[0]["flags"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
