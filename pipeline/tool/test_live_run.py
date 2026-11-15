"""Tests for live mode (T58). No model calls: a pretend client gives back the replies
Sonnet 5.5 really gave for the demo patient D001 (run 20261115-v2-demo-sonnet-5-5).
Everything is written to a temporary folder, never to the real outputs/ or app/data/.

Run: python pipeline/tool/test_live_run.py
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
import live_run  # noqa: E402
import run_records  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DEMO = REPO / "pipeline" / "data" / "demo" / "D001"
SAVED = REPO / "outputs" / "extracted" / "20261115-v2-demo-sonnet-5-5"


class ReplayD001:
    """Answers each record with the real saved reply for the matching D001 record."""

    def __init__(self):
        self.calls = []
        self.by_text = {}
        for h, ext in (("A", "csv"), ("B", "txt"), ("C", "txt")):
            text = (DEMO / f"D001_{h}.{ext}").read_text(encoding="utf-8")
            self.by_text[text] = (SAVED / f"D001_{h}.raw.txt").read_text(encoding="utf-8")
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        reply = self.by_text[kw["messages"][0]["content"]]
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=reply)],
                               usage=SimpleNamespace(input_tokens=1000, output_tokens=200),
                               stop_reason="end_turn", id="msg_test", model=kw["model"])


class NoCalls:
    messages = SimpleNamespace(create=lambda **kw: (_ for _ in ()).throw(AssertionError("no call expected")))


class LiveRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        # Point every module at the temporary folder: outputs, the data folders, the app's live folder.
        self.old = (extract.OUTPUTS, check.OUTPUTS, check.DATA, run_records.DATA,
                    live_run.DATA, live_run.APP_LIVE)
        extract.OUTPUTS = check.OUTPUTS = root / "outputs"
        data = root / "data"
        (data / "demo").mkdir(parents=True)
        check.DATA = run_records.DATA = live_run.DATA = data
        live_run.APP_LIVE = root / "app_live"
        self.inputs = [str(DEMO / "D001_A.csv"), str(DEMO / "D001_B.txt"), str(DEMO / "D001_C.txt")]
        self.opened = []

    def tearDown(self):
        (extract.OUTPUTS, check.OUTPUTS, check.DATA, run_records.DATA,
         live_run.DATA, live_run.APP_LIVE) = self.old
        self.tmp.cleanup()

    def run_live(self, argv, client=None, answer="yes"):
        return live_run.main(argv + ["--no-open"], client=client, ask=lambda _: answer,
                             opener=self.opened.append)

    def test_full_run_makes_three_calls_and_gives_the_app_a_merged_record(self):
        client = ReplayD001()
        self.assertEqual(self.run_live(self.inputs, client), 0)
        self.assertEqual(len(client.calls), 3)
        for kw in client.calls:                                   # frozen settings (T56)
            self.assertEqual(kw["model"], "claude-sonnet-5-5")
            self.assertNotIn("temperature", kw)
        index = json.loads((live_run.APP_LIVE / "index.json").read_text(encoding="utf-8"))
        entry = index["patients"][0]
        self.assertEqual(entry["patient_id"], "D901")
        self.assertIn("-v2-live-D901-sonnet-5-5", entry["run_id"])
        self.assertEqual(entry["source_files"], ["D001_A.csv", "D001_B.txt", "D001_C.txt"])
        record = json.loads((live_run.APP_LIVE / "D901_compiled.json").read_text(encoding="utf-8"))
        self.assertEqual(record["patient_id"], "D901")
        # Same readings as the demo run, so the same merged record: 7 facts, the penicillin conflict.
        self.assertEqual(len(record["facts"]), 7)
        self.assertEqual(entry["conflicts"], 1)
        self.assertEqual(compile_problems(record), [])

    def test_no_means_no_calls_and_nothing_copied(self):
        self.assertEqual(self.run_live(self.inputs, NoCalls(), answer="no"), 0)
        self.assertFalse((live_run.DATA / "demo" / "D901").exists())
        self.assertFalse(live_run.APP_LIVE.exists())

    def test_dry_run_makes_no_calls(self):
        self.assertEqual(self.run_live(self.inputs + ["--dry-run"], NoCalls()), 0)
        self.assertFalse((live_run.DATA / "demo" / "D901").exists())

    def test_demo_option_uses_d001_records(self):
        self.assertEqual(self.run_live(["--demo"], ReplayD001()), 0)
        self.assertTrue((live_run.DATA / "demo" / "D901" / "D901_C.txt").exists())

    def test_second_run_gets_the_next_id(self):
        self.run_live(self.inputs, ReplayD001())
        self.run_live(self.inputs, ReplayD001())
        index = json.loads((live_run.APP_LIVE / "index.json").read_text(encoding="utf-8"))
        self.assertEqual([p["patient_id"] for p in index["patients"]], ["D901", "D902"])

    def test_show_reopens_without_calls(self):
        self.run_live(self.inputs, ReplayD001())
        self.assertEqual(live_run.main(["--show", "d901", "--no-open"], client=NoCalls(), opener=self.opened.append,
                                       ask=lambda _: "no"), 0)
        with self.assertRaises(SystemExit):
            live_run.main(["--show", "D950", "--no-open"])

    def test_bad_inputs_are_refused(self):
        tmp = Path(self.tmp.name)
        empty = tmp / "empty.txt"
        empty.write_text("", encoding="utf-8")
        word = tmp / "letter.docx"
        word.write_text("x", encoding="utf-8")
        hidden = tmp / "P050_A.csv"
        hidden.write_text("x", encoding="utf-8")
        for files in ([str(empty)] + self.inputs[1:],
                      [str(word)] + self.inputs[1:],
                      [str(hidden)] + self.inputs[1:],
                      self.inputs[:2],
                      [str(tmp / "missing.csv")] + self.inputs[1:]):
            with self.assertRaises(SystemExit):
                self.run_live(files, NoCalls())
        with self.assertRaises(SystemExit):
            self.run_live(["--demo"] + self.inputs, NoCalls())

    def test_frozen_files_exist(self):
        for name in live_run.FROZEN_FILES:
            self.assertTrue((REPO / name).is_file(), name)


def compile_problems(record):
    return live_run.compile_step.validate(record)


if __name__ == "__main__":
    unittest.main()
