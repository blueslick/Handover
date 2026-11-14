"""Daniel's checks for the Check step (T22). No model calls, no held-out data.

Run: python pipeline/tool/test_check.py

Two kinds of test:
  * Perfect readings. The record makers (T05, T13) know exactly which facts each hospital
    record states. Those facts, wrapped as if the model had returned them, must pass the
    Check step with no problems, for the demo patient D001 and all 20 working patients.
  * Mistakes. Made-up model replies with one thing wrong each (quote not in the record,
    wrong dose, brand left in, unknown name, bad shape...) must be caught or tidied, and
    the retry must happen once, and only when a check fails.
"""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parent
REPO = TOOL.parent.parent
sys.path.insert(0, str(TOOL))
sys.path.insert(0, str(REPO / "pipeline" / "data"))
sys.path.insert(0, str(REPO / "shared"))

import check  # noqa: E402
from check import check_record, check_with_retry  # noqa: E402
import validate  # noqa: E402  (shared/validate.py)

D001 = REPO / "pipeline" / "data" / "demo" / "D001"
WORKING = [f"P{n:03d}" for n in range(1, 21)]


def wrap(patient_id, hospital, source_file, facts, attempt=1):
    """Wrap facts in the extracted-file shape, as the extract step will save them."""
    return {"format_version": "1.0", "patient_id": patient_id, "hospital": hospital,
            "source_file": source_file, "run_id": "20261115-test-none", "model": "none",
            "prompt_version": "v0", "temperature": 0, "attempt": attempt,
            "usage": {"input_tokens": 0, "output_tokens": 0}, "facts": facts}


def read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def is_valid(doc):
    """Run shared/validate.py's checks on a checked record."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "x.json"
        import json
        p.write_text(json.dumps(doc), encoding="utf-8")
        return validate.check_file(p, "extracted")


def fact(type_="medicine", name="paracetamol", written="Panadol", dose="1000 mg",
         freq="as_needed", status="current", quote="2. Panadol 1 g PRN", reaction=None,
         date="2021-10-05", flags=None):
    return {"type": type_, "name": name, "name_as_written": written, "dose": dose,
            "frequency": freq, "reaction": reaction, "status": status, "date": date,
            "quote": quote, "flags": flags or []}


C_TEXT = read(D001 / "D001_C.txt")


def one(f):
    """Check one fact against Hospital C's record for D001."""
    return check_record(wrap("D001", "C", "D001_C.txt", [f]), C_TEXT)


class PerfectReadingsPass(unittest.TestCase):
    def assert_passes(self, patient_id, records, folder):
        for r in records:
            doc = wrap(patient_id, r["hospital"], r["file"], copy.deepcopy(r["facts"]))
            result = check_record(doc, read(folder / r["file"]))
            self.assertEqual(result["problems"], [], f"{r['file']}")
            self.assertEqual(is_valid(result["checked"]), [], f"{r['file']}")
            for f in result["checked"]["facts"]:
                self.assertNotIn("unverified", f["flags"], f"{r['file']}: {f['quote']}")
                self.assertNotIn("unknown_name", f["flags"], f"{r['file']}: {f['quote']}")

    def test_demo_patient(self):
        import make_demo_patient as demo
        records = []
        for visit in demo.VISITS:
            _, facts = demo.render(visit)
            records.append({"hospital": visit["hospital"],
                            "file": "D001" + demo.FILE_ENDINGS[visit["hospital"]],
                            "facts": [dict(f, flags=[]) for f in facts]})
        self.assert_passes("D001", records, D001)

    def test_working_patients(self):
        import make_hospital_records as mhr
        for pid in WORKING:
            self.assert_passes(pid, mhr.written_facts(pid), REPO / "pipeline" / "data" / "working" / pid)

    def test_brands_filled_in_when_model_leaves_name_blank(self):
        # The model may leave name empty and only copy what was written; the tables fill it.
        import make_hospital_records as mhr
        for pid in WORKING:
            for r in mhr.written_facts(pid):
                facts = copy.deepcopy(r["facts"])
                expected = [f["name"] for f in facts]
                for f in facts:
                    if f["type"] in ("allergy", "medicine"):
                        f["name"] = None
                folder = REPO / "pipeline" / "data" / "working" / pid
                out = check_record(wrap(pid, r["hospital"], r["file"], facts), read(folder / r["file"]))
                got = [f["name"] for f in out["checked"]["facts"]]
                self.assertEqual(got, expected, r["file"])


class Tidying(unittest.TestCase):
    def test_grams_become_milligrams(self):
        out = one(fact(dose="1 g"))
        self.assertEqual(out["problems"], [])
        self.assertEqual(out["checked"]["facts"][0]["dose"], "1000 mg")

    def test_brand_converted(self):
        out = one(fact(name="Glucophage", written="Glucophage", dose="1000 mg",
                       freq="twice_daily", quote="1. Glucophage 1 g BD"))
        self.assertEqual(out["checked"]["facts"][0]["name"], "metformin")

    def test_longest_brand_first(self):
        text = "1. Glucophage XR 500 mg OD"
        out = check_record(wrap("D001", "C", "D001_C.txt", [fact(
            name=None, written="Glucophage XR", dose="500 mg", freq="daily", quote=text)]), text)
        self.assertEqual(out["checked"]["facts"][0]["name"], "metformin")

    def test_combination_not_cut_down(self):
        self.assertEqual(check.to_generic("amoxicillin / clavulanate", None), "amoxicillin / clavulanate")
        self.assertEqual(check.to_generic("Augmentin", "amoxicillin"), "amoxicillin / clavulanate")

    def test_combination_written_with_and(self):
        self.assertEqual(check.to_generic("amoxicillin and clavulanate", None), "amoxicillin / clavulanate")
        self.assertEqual(check.to_generic("Tylenol with Codeine", None), "paracetamol / codeine")
        self.assertEqual(check.to_generic("Humulin 70/30", None), "insulin isophane / insulin regular")

    def test_every_table_name_converts(self):
        import csv
        with open(REPO / "shared" / "brand_to_generic.csv", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                self.assertEqual(check.to_generic(row["brand"], None), row["generic"].lower(), row["brand"])

    def test_capitals_ignored(self):
        self.assertEqual(check.to_generic("PANADOL", None), "paracetamol")

    def test_missing_dose_flag(self):
        out = one(fact(dose=None, quote="2. Panadol 1 g PRN"))
        self.assertIn("missing_dose", out["checked"]["facts"][0]["flags"])
        self.assertEqual(out["problems"], [])

    def test_line_breaks_may_differ(self):
        out = one(fact(type_="allergy", name=None, written="NKA", dose=None, freq=None,
                       status="none_recorded", quote="[ALLERGIES]\n - NKA"))
        self.assertEqual(out["problems"], [])

    def test_none_recorded_has_no_name(self):
        out = one(fact(type_="allergy", name="nka", written="NKA", dose=None, freq=None,
                       status="none_recorded", quote="- NKA"))
        self.assertIsNone(out["checked"]["facts"][0]["name"])


class MistakesCaught(unittest.TestCase):
    def assert_flagged(self, out, word):
        self.assertTrue(any(word in p for p in out["problems"]), out["problems"])
        self.assertIn("unverified", out["checked"]["facts"][0]["flags"])
        self.assertEqual(is_valid(out["checked"]), [])

    def test_made_up_quote(self):
        self.assert_flagged(one(fact(quote="Panadol 500 mg PRN")), "quote not found")

    def test_tidied_quote(self):
        # Changing capitals or words is not allowed; only spacing may differ.
        self.assert_flagged(one(fact(quote="2. panadol 1 g PRN")), "quote not found")

    def test_name_not_in_quote(self):
        self.assert_flagged(one(fact(written="Glucophage")), "name as written")

    def test_wrong_dose(self):
        self.assert_flagged(one(fact(dose="500 mg")), "dose")

    def test_ten_is_not_one(self):
        self.assertFalse(check.dose_in_quote("1 mg", "Warfarin 10 mg"))
        self.assertTrue(check.dose_in_quote("1000 mg", "1. Glucophage 1 g BD"))
        self.assertTrue(check.dose_in_quote("2.5 mg", "Amlodipine,2.5 mg,once daily"))

    def test_status_not_allowed(self):
        out = one(fact(status="family_history"))
        self.assertTrue(any("not allowed" in p for p in out["problems"]))

    def test_unknown_name_flagged_not_guessed(self):
        text = "1. Zzyxol 5 mg OD"
        out = check_record(wrap("D001", "C", "D001_C.txt", [fact(
            name="zzyxol", written="Zzyxol", dose="5 mg", freq="daily", quote=text)]), text)
        f = out["checked"]["facts"][0]
        self.assertIsNone(f["name"])
        self.assertIn("unknown_name", f["flags"])
        self.assertEqual(out["problems"], [])   # an unknown name alone does not earn a retry
        self.assertEqual(is_valid(out["checked"]), [])

    def test_bad_shape(self):
        doc = wrap("D001", "C", "D001_C.txt", [fact()])
        del doc["facts"][0]["quote"]
        out = check_record(doc, C_TEXT)
        self.assertIsNone(out["checked"])
        self.assertTrue(out["problems"])


class OneRetry(unittest.TestCase):
    def test_no_retry_when_it_passes(self):
        calls = []
        r = check_with_retry(wrap("D001", "C", "D001_C.txt", [fact()]), C_TEXT,
                             lambda p: calls.append(p))
        self.assertEqual(calls, [])
        self.assertEqual((r["attempt"], r["retried"]), (1, False))

    def test_one_retry_when_it_fails_and_the_better_try_is_kept(self):
        calls = []

        def again(problems):
            calls.append(problems)
            return wrap("D001", "C", "D001_C.txt", [fact()], attempt=2)

        r = check_with_retry(wrap("D001", "C", "D001_C.txt", [fact(quote="made up")]), C_TEXT, again)
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0])                     # the problems are passed to the retry
        self.assertEqual((r["attempt"], r["retried"], r["problems"]), (2, True, []))

    def test_worse_retry_is_not_kept(self):
        bad_shape = {"facts": "oops"}
        r = check_with_retry(wrap("D001", "C", "D001_C.txt", [fact(quote="made up")]), C_TEXT,
                             lambda p: bad_shape)
        self.assertEqual(r["attempt"], 1)
        self.assertIn("unverified", r["checked"]["facts"][0]["flags"])

    def test_still_failing_after_retry_is_kept_with_flags(self):
        calls = []

        def again(problems):
            calls.append(1)
            return wrap("D001", "C", "D001_C.txt", [fact(quote="still made up")], attempt=2)

        r = check_with_retry(wrap("D001", "C", "D001_C.txt", [fact(quote="made up")]), C_TEXT, again)
        self.assertEqual(len(calls), 1)               # never a third try
        self.assertTrue(r["problems"])
        self.assertIn("unverified", r["checked"]["facts"][0]["flags"])


class CommandLine(unittest.TestCase):
    def test_run_reads_saved_files_and_lists_retries(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            old = check.OUTPUTS
            check.OUTPUTS = Path(tmp)
            try:
                ext = Path(tmp) / "extracted" / "t"
                ext.mkdir(parents=True)
                good = wrap("D001", "C", "D001_C.txt", [fact()])
                bad = wrap("D001", "B", "D001_B.txt", [fact(quote="made up")])
                (ext / "D001_C.json").write_text(json.dumps(good), encoding="utf-8")
                (ext / "D001_B.json").write_text(json.dumps(bad), encoding="utf-8")
                rep = check.run("t")
                self.assertEqual(rep["needs_retry"], ["D001_B"])
                self.assertTrue((Path(tmp) / "checked" / "t" / "D001_C.json").exists())

                # Once the retry is saved, the next run uses it and nothing needs a retry.
                fixed_b = wrap("D001", "B", "D001_B.txt", [fact(
                    name="metformin", written="metformin", dose="1000 mg", freq="twice_daily",
                    quote="She takes metformin 1000 mg twice a day.")], attempt=2)
                (ext / "D001_B.attempt2.json").write_text(json.dumps(fixed_b), encoding="utf-8")
                rep = check.run("t")
                self.assertEqual(rep["needs_retry"], [])
                self.assertEqual(rep["records"]["D001_B"]["attempt_kept"], 2)
            finally:
                check.OUTPUTS = old


if __name__ == "__main__":
    unittest.main(verbosity=1)
