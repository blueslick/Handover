"""Tests for the extract step (T19). No model calls: a pretend client gives the reply.

Run: python pipeline/tool/test_extract.py
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract  # noqa: E402

DEMO = extract.REPO / "pipeline" / "data" / "demo" / "D001"

# What a correct reading of D001_C.txt looks like (copied from the record by hand).
GOOD_C = {"facts": [
    {"type": "allergy", "name": None, "name_as_written": "NKA", "dose": None, "frequency": None,
     "reaction": None, "status": "none_recorded", "date": "2021-10-05", "quote": "- NKA"},
    {"type": "diagnosis", "name": "type 2 diabetes", "name_as_written": "Type 2 diabetes", "dose": None,
     "frequency": None, "reaction": None, "status": "current", "date": "2021-10-05", "quote": "- Type 2 diabetes"},
    {"type": "medicine", "name": "metformin", "name_as_written": "Glucophage", "dose": "1 g",
     "frequency": "twice_daily", "reaction": None, "status": "current", "date": "2021-10-05",
     "quote": "1. Glucophage 1 g BD"},
    {"type": "medicine", "name": "paracetamol", "name_as_written": "Panadol", "dose": "1 g",
     "frequency": "as_needed", "reaction": None, "status": "current", "date": "2021-10-05",
     "quote": "2. Panadol 1 g PRN"},
]}


class FakeClient:
    def __init__(self, reply_text):
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)
        self._reply = reply_text

    def _create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(
            content=[SimpleNamespace(type="thinking", thinking="..."),
                     SimpleNamespace(type="text", text=self._reply)],
            usage=SimpleNamespace(input_tokens=1500, output_tokens=400),
            stop_reason="end_turn", id="msg_test", model=kw["model"])


class ExtractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        extract.OUTPUTS = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_once(self, reply, model="claude-sonnet-5-5", record="D001_C.txt"):
        client = FakeClient(json.dumps(reply) if isinstance(reply, dict) else reply)
        code = extract.main(["--model", model, "--record", str(DEMO / record), "--run-id", "20261115-test-v1"],
                            client=client)
        return code, client

    def folder(self):
        return extract.OUTPUTS / "extracted" / "20261115-test-v1"

    def saved(self, stem="D001_C"):
        return json.loads((self.folder() / f"{stem}.json").read_text(encoding="utf-8"))

    def test_good_reply_saves_a_valid_file(self):
        code, client = self.run_once(GOOD_C)
        self.assertEqual(code, 0)
        self.assertEqual(len(client.calls), 1)                     # exactly one call
        self.assertEqual(extract.validate_record(self.folder() / "D001_C.json"), [])
        rec = self.saved()
        self.assertEqual(rec["usage"], {"input_tokens": 1500, "output_tokens": 400})
        self.assertEqual(rec["patient_id"], "D001")
        self.assertEqual(rec["hospital"], "C")
        self.assertIsNone(rec["temperature"])
        raw = (self.folder() / "D001_C.raw.txt").read_text(encoding="utf-8")
        self.assertEqual(json.loads(raw), GOOD_C)                  # exact reply kept

    def test_settings_sent(self):
        _, client = self.run_once(GOOD_C)
        kw = client.calls[0]
        self.assertEqual(kw["thinking"], {"type": "between_tools"})
        self.assertEqual(kw["output_config"]["format"]["type"], "json_schema")
        self.assertNotIn("temperature", kw)
        self.assertIn("Copy what the record says", kw["system"])
        _, client = self.run_once(GOOD_C, model="claude-haiku-5-5", record="D001_B.txt")
        self.assertNotIn("thinking", client.calls[0])              # Haiku refused between_tools in T08

    def test_only_required_flags_are_added(self):
        reply = {"facts": [dict(GOOD_C["facts"][3], dose=None),       # current, no dose
                           dict(GOOD_C["facts"][2], name=None)]}      # brand the model didn't know
        self.run_once(reply)
        flags = [f["flags"] for f in self.saved()["facts"]]
        self.assertEqual(flags, [["missing_dose"], ["unknown_name"]])

    def test_bad_quote_is_reported_not_fixed(self):
        reply = {"facts": [dict(GOOD_C["facts"][3], quote="Panadol 1g PRN")]}
        self.run_once(reply)
        self.assertEqual(self.saved()["facts"][0]["quote"], "Panadol 1g PRN")
        text = (DEMO / "D001_C.txt").read_text(encoding="utf-8")
        self.assertEqual(extract.quotes_not_in_record(self.saved()["facts"], text), ["Panadol 1g PRN"])

    def test_not_json_keeps_raw_reply(self):
        code, _ = self.run_once("sorry, here are the facts: ...")
        self.assertEqual(code, 1)
        self.assertTrue((self.folder() / "D001_C.raw.txt").exists())
        self.assertFalse((self.folder() / "D001_C.json").exists())

    def test_goes_through_saved_calls(self):
        """T20: the call is saved with its details, and a saved reply is replayed with no call."""
        self.run_once(GOOD_C)
        details = json.loads((self.folder() / "D001_C.call.json").read_text(encoding="utf-8"))
        self.assertEqual(details["usage"]["input_tokens"], 1500)
        self.assertEqual(details["prompt_version"], "v1")
        (self.folder() / "D001_C.json").unlink()       # wrapper gone, saved reply kept
        code, client = self.run_once(GOOD_C)
        self.assertEqual(code, 0)
        self.assertEqual(client.calls, [])              # replayed, no new call
        self.assertEqual(self.saved()["usage"]["output_tokens"], 400)

    def test_never_overwrites(self):
        self.run_once(GOOD_C)
        with self.assertRaises(SystemExit):
            self.run_once(GOOD_C)

    def test_refuses_heldout_and_non_records(self):
        for bad in [extract.REPO / "pipeline/data/heldout/P021/P021_A.csv",
                    DEMO / "D001_key.json"]:
            with self.assertRaises(SystemExit):
                extract.check_record_path(bad)

    def test_dry_run_makes_no_call(self):
        client = FakeClient("{}")
        extract.main(["--model", "claude-sonnet-5-5", "--record", str(DEMO / "D001_A.csv"),
                      "--run-id", "20261115-test-v1", "--dry-run"], client=client)
        self.assertEqual(client.calls, [])

    def test_prompt_examples_are_real_quotes(self):
        """The quote examples in the prompt are copied from the demo records, character for character."""
        prompt = (extract.PROMPTS / "extract_v1.md").read_text(encoding="utf-8")
        records = "".join((DEMO / f"D001_{h}").read_text(encoding="utf-8") for h in ("A.csv", "B.txt", "C.txt"))
        for q in ["MEDICATION,Metformin,500 mg,twice daily,Active,2017-04-10,", "1. Glucophage 1 g BD",
                  "- NKA", "Her warfarin was stopped on 20 June 2021."]:
            self.assertIn(q, prompt)
            self.assertIn(q, records)

    def test_reply_schema_matches_fixed_lists(self):
        s = extract.reply_schema()["properties"]["facts"]["items"]
        self.assertEqual(set(s["required"]),
                         set(json.loads((extract.SHARED / "schema" / "extracted.schema.json").read_text())
                             ["$defs"]["fact"]["required"]) - {"flags"})


# Plain lists (T66, results-table row 4): the same reading with no status and no "NKA" line.
PLAIN_C = {"facts": [{k: v for k, v in f.items() if k != "status"} for f in GOOD_C["facts"][1:]]}


class PlainListTests(unittest.TestCase):
    """The plain-lists prompt (extract_v2-plain.md): no status asked for, every fact saved as current."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        extract.OUTPUTS = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_plain(self, reply=PLAIN_C):
        client = FakeClient(json.dumps(reply))
        code = extract.main(["--model", "claude-sonnet-5-5", "--record", str(DEMO / "D001_C.txt"),
                             "--prompt", "v2-plain", "--run-id", "20261115-test-v2-plain"], client=client)
        folder = extract.OUTPUTS / "extracted" / "20261115-test-v2-plain"
        return code, client, folder

    def test_only_versions_ending_in_plain_are_plain(self):
        self.assertTrue(extract.is_plain("v2-plain"))
        for v in ("v1", "v2", "v2-demo", "v2-plainer"):
            self.assertFalse(extract.is_plain(v))

    def test_reply_shape_has_no_status_and_the_normal_shape_is_unchanged(self):
        plain = extract.reply_schema(plain=True)["properties"]["facts"]["items"]
        normal = extract.reply_schema()["properties"]["facts"]["items"]
        self.assertNotIn("status", plain["required"])
        self.assertNotIn("status", plain["properties"])
        self.assertIn("status", normal["required"])
        self.assertEqual(set(normal["required"]) - {"status"}, set(plain["required"]))

    def test_plain_prompt_never_asks_for_a_status(self):
        prompt = (extract.PROMPTS / "extract_v2-plain.md").read_text(encoding="utf-8")
        self.assertNotIn("status", prompt.replace("StatusDate", "").lower())
        self.assertNotIn("none_recorded", prompt)
        records = "".join((DEMO / f"D001_{h}").read_text(encoding="utf-8") for h in ("A.csv", "B.txt", "C.txt"))
        for q in ["MEDICATION,Metformin,500 mg,twice daily,Active,2017-04-10,", "1. Glucophage 1 g BD",
                  "Her warfarin was stopped on 20 June 2021."]:
            self.assertIn(q, prompt)        # quote examples are still real quotes
            self.assertIn(q, records)

    def test_every_plain_fact_is_saved_as_current_and_the_file_is_valid(self):
        code, client, folder = self.run_plain()
        self.assertEqual(code, 0)
        kw = client.calls[0]
        self.assertNotIn("status", json.dumps(kw["output_config"]))     # the model is not asked for one
        self.assertIn("plain list", kw["system"])
        self.assertEqual(extract.validate_record(folder / "D001_C.json"), [])
        rec = json.loads((folder / "D001_C.json").read_text(encoding="utf-8"))
        self.assertEqual(rec["prompt_version"], "v2-plain")
        self.assertEqual({f["status"] for f in rec["facts"]}, {"current"})
        self.assertIn("plain lists", rec["settings"])
        self.assertEqual(json.loads((folder / "D001_C.raw.txt").read_text(encoding="utf-8")), PLAIN_C)

    def test_a_plain_run_is_never_retried(self):
        with self.assertRaises(ValueError):
            extract.extract_once(model="claude-sonnet-5-5", record_path=DEMO / "D001_C.txt",
                                 prompt_version="v2-plain", run_id="20261115-test-v2-plain",
                                 client=FakeClient("{}"), attempt=2, problems=["x"], first_reply_text="{}")


if __name__ == "__main__":
    unittest.main(verbosity=1)
