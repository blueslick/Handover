"""Tests for the many-records runner and the one retry. No model calls: a pretend
client gives the replies. Uses the demo patient D001 only.

Run: python pipeline/tool/test_run_records.py
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check  # noqa: E402
import extract  # noqa: E402
import run_records  # noqa: E402
from test_extract import GOOD_C  # noqa: E402  (a correct reading of D001_C.txt)

RUN = "20261115-test-v1"
BAD_C = {"facts": [dict(GOOD_C["facts"][3], quote="Panadol 1g PRN")]}   # quote not in the record
EMPTY = {"facts": []}                                                    # passes the check


class FakeClient:
    """Replies by hospital: for D001_C.txt, `c_replies` in order (first try, retry)."""

    def __init__(self, c_replies):
        self.calls = []
        self.c_replies = list(c_replies)
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        is_c = "Glucophage" in kw["messages"][0]["content"]
        reply = self.c_replies.pop(0) if is_c else EMPTY
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(reply))],
                               usage=SimpleNamespace(input_tokens=1000, output_tokens=200),
                               stop_reason="end_turn", id="msg_test", model=kw["model"])


class NoCalls:
    messages = SimpleNamespace(create=lambda **kw: (_ for _ in ()).throw(AssertionError("no call expected")))


class RunRecordsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = (extract.OUTPUTS, check.OUTPUTS)
        extract.OUTPUTS = check.OUTPUTS = Path(self.tmp.name)

    def tearDown(self):
        extract.OUTPUTS, check.OUTPUTS = self.old
        self.tmp.cleanup()

    def run_d001(self, client, *extra):
        return run_records.main(["--model", "claude-sonnet-5-5", "--patients", "D001", "--run-id", RUN,
                                 "--no-compile", *extra], client=client)

    def folder(self, kind="extracted"):
        return extract.OUTPUTS / kind / RUN

    def test_passing_records_make_one_call_each(self):
        client = FakeClient([GOOD_C])
        self.assertEqual(self.run_d001(client), 0)
        self.assertEqual(len(client.calls), 3)
        self.assertFalse(list(self.folder().glob("*.attempt2.*")))
        self.assertTrue((self.folder("checked") / "D001_C.json").exists())
        self.assertTrue((self.folder() / "usage.csv").exists())

    def test_failed_check_gets_one_retry_with_the_problems(self):
        client = FakeClient([BAD_C, GOOD_C])
        self.run_d001(client)
        self.assertEqual(len(client.calls), 4)                       # 3 records + 1 retry
        retry = client.calls[-1]["messages"]
        self.assertEqual([m["role"] for m in retry], ["user", "assistant", "user"])
        self.assertEqual(json.loads(retry[1]["content"]), BAD_C)     # the first reply goes back
        self.assertIn("quote not found in the record", retry[2]["content"])
        second = json.loads((self.folder() / "D001_C.attempt2.json").read_text(encoding="utf-8"))
        self.assertEqual(second["attempt"], 2)
        report = json.loads((self.folder("checked") / "check_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["records"]["D001_C"]["attempt_kept"], 2)
        self.assertTrue(report["records"]["D001_C"]["passed"])

    def test_never_a_third_call(self):
        client = FakeClient([BAD_C, BAD_C])
        self.run_d001(client)
        self.assertEqual(len(client.calls), 4)
        report = json.loads((self.folder("checked") / "check_report.json").read_text(encoding="utf-8"))
        self.assertFalse(report["records"]["D001_C"]["passed"])     # kept, flagged, not called again
        kept = json.loads((self.folder("checked") / "D001_C.json").read_text(encoding="utf-8"))
        self.assertIn("unverified", kept["facts"][0]["flags"])

    def test_running_again_makes_no_calls(self):
        self.run_d001(FakeClient([BAD_C, GOOD_C]))
        self.assertEqual(self.run_d001(NoCalls()), 0)                # replays the saved files

    def test_more_than_ten_calls_needs_yes(self):
        ids = ["P001", "P002", "P003", "P004"]                       # 12 calls
        code = run_records.main(["--model", "claude-sonnet-5-5", "--patients", *ids, "--run-id", RUN,
                                 "--no-compile"], client=NoCalls())
        self.assertEqual(code, 0)
        self.assertFalse(self.folder().exists())

    def test_heldout_refused(self):
        with self.assertRaises(SystemExit):
            run_records.main(["--model", "claude-sonnet-5-5", "--patients", "P050", "--dry-run"])
        with self.assertRaises(SystemExit):
            run_records.main(["--model", "claude-sonnet-5-5", "--patients", "R001", "--dry-run"])
        if not run_records.freeze_tag_exists():
            with self.assertRaises(SystemExit):
                run_records.main(["--model", "claude-sonnet-5-5", "--patients", "P050", "--heldout",
                                  "--dry-run"])

    def test_haiku_retry_keeps_its_settings(self):
        client = FakeClient([BAD_C, GOOD_C])
        run_records.main(["--model", "claude-haiku-5-5", "--patients", "D001", "--run-id", RUN,
                          "--no-compile"], client=client)
        for kw in client.calls:
            self.assertNotIn("temperature", kw)
            self.assertNotIn("thinking", kw)                         # Haiku refused between_tools (T08)


if __name__ == "__main__":
    unittest.main()
