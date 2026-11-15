"""Tests for the single-note helper (T43, shared with T40). No model calls: a fake client gives the replies.

Each test works in its own temporary folder, with a tiny git repo that holds the frozen
files and a `freeze` tag (live_run.REPO and run_records.REPO are pointed at that repo). So no
real note, output or frozen file is written. The one test that reads the real repo only asks
git to compare files.

Run: python pipeline/tool/test_run_single_notes.py
"""
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compile as compile_step  # noqa: E402
import live_run  # noqa: E402
import run_records  # noqa: E402
import run_single_notes as rsn  # noqa: E402

RUN = "20261115-test-v2-sonnet-5-5"
NOTE = "Diagnoses: Type 2 diabetes.\nMedications: 1. Glucophage 1 g BD\n"

# A correct reading of NOTE: every quote is word for word in the note.
GOOD = {"facts": [
    {"type": "diagnosis", "name": "type 2 diabetes", "name_as_written": "Type 2 diabetes", "dose": None,
     "frequency": None, "reaction": None, "status": "current", "date": "2026-01-05",
     "quote": "Type 2 diabetes"},
    {"type": "medicine", "name": "metformin", "name_as_written": "Glucophage", "dose": "1 g",
     "frequency": "twice_daily", "reaction": None, "status": "current", "date": "2026-01-05",
     "quote": "Glucophage 1 g BD"},
]}
# A wrong reading: the quote and the dose are not in the note, so the Check step fails it.
BAD = {"facts": [dict(GOOD["facts"][1], quote="Glucophage 2 g BD")]}
EMPTY = {"facts": []}


class FakeClient:
    """Gives the replies in order, one per call, and records each request (the pretend model)."""

    def __init__(self, replies):
        self.calls = []
        self.replies = list(replies)
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        reply = self.replies.pop(0)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(reply))],
                               usage=SimpleNamespace(input_tokens=1200, output_tokens=150),
                               stop_reason="end_turn", id="msg_test", model=kw["model"])


class NoCalls:
    """Fails the test if anything tries to call the model."""

    def __init__(self):
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        raise AssertionError("no model call expected here")


class SingleNoteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.paths = rsn.Paths(data=self.root / "pipeline" / "data", outputs=self.root / "outputs")
        self.make_frozen_repo()
        # The freeze check reads the temporary repo, not the real one.
        for module in (live_run, run_records):
            patcher = mock.patch.object(module, "REPO", self.root)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.write_note("D201")

    def tearDown(self):
        self.tmp.cleanup()

    # ---- helpers

    def make_frozen_repo(self):
        """A tiny git repo: the frozen files (as live_run lists them), committed and tagged `freeze`."""
        git = ["git", "-C", str(self.root)]
        subprocess.run([*git, "init", "-q"], check=True)
        for rel in live_run.FROZEN_FILES:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"frozen {rel}\n", encoding="utf-8")
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run([*git, "-c", "user.name=test", "-c", "user.email=test@example.invalid",
                        "-c", "commit.gpgsign=false", "commit", "-q", "-m", "frozen"], check=True)
        subprocess.run([*git, "tag", "freeze"], check=True)

    def write_note(self, pid, letter="B", text=NOTE, ext="txt"):
        folder = self.paths.demo / pid
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{pid}_{letter}.{ext}").write_text(text, encoding="utf-8")

    def run_cmd(self, argv, client=None):
        """Run the command with its printing captured. Returns (exit code, printed text)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = rsn.main(argv, client=client, paths=self.paths)
        return code, out.getvalue()

    def saved(self, kind, name=""):
        """A path under outputs/<kind>/<RUN>/ (the real run's folders)."""
        return self.paths.outputs / kind / RUN / name

    # ---- which IDs

    def test_allowed_ids(self):
        self.assertEqual(rsn.parse_ids(["D201-D212"]), [f"D{n}" for n in range(201, 213)])
        self.assertEqual(rsn.parse_ids(["D203", "D201", "D203"]), ["D203", "D201"])   # order kept, repeats dropped
        self.assertEqual(len(rsn.TRAP_IDS), 40)
        self.assertEqual(rsn.TRAP_IDS[0], "D101")
        self.assertEqual(rsn.TRAP_IDS[-1], "D140")

    def test_other_ids_are_refused(self):
        for bad in (["D001"], ["D901"], ["P001"], ["R001"], ["D141"], ["D200"], ["D213"], ["D21"],
                    ["D212-D201"], ["D001-D003"]):
            with self.subTest(ids=bad):
                with self.assertRaises(SystemExit):
                    rsn.parse_ids(bad)

    def test_must_say_which_notes(self):
        with self.assertRaises(SystemExit):
            self.run_cmd(["--run-id", RUN, "--dry-run"])

    def test_run_id_is_required_and_held_out_refused(self):
        with self.assertRaises(SystemExit):
            self.run_cmd(["--notes", "D201", "--dry-run"])                          # no --run-id
        with self.assertRaises(SystemExit):
            self.run_cmd(["--notes", "D201", "--run-id", "20261115-heldout-test", "--dry-run"])
        with self.assertRaises(SystemExit):
            self.run_cmd(["--notes", "D201", "--run-id", "not-a-run-id", "--dry-run"])

    def test_no_model_or_prompt_option(self):
        for extra in (["--model", "claude-haiku-5-5"], ["--prompt", "v1"]):
            with self.subTest(extra=extra):
                with self.assertRaises(SystemExit):
                    self.run_cmd(["--notes", "D201", "--run-id", RUN, "--dry-run", *extra])

    # ---- one record per note folder

    def test_exactly_one_record_per_folder(self):
        self.write_note("D203", "A", ext="csv")                  # any letter, csv or txt
        self.write_note("D204", "B")
        (self.paths.demo / "D204" / "D204_key.json").write_text("{}\n", encoding="utf-8")   # not a record: ignored
        code, out = self.run_cmd(["--notes", "D203", "D204", "--run-id", RUN, "--dry-run"], NoCalls())
        self.assertEqual(code, 0)
        self.assertIn("D203 (D203_A.csv)", out)
        self.assertIn("D204 (D204_B.txt)", out)

    def test_zero_records_stops(self):
        (self.paths.demo / "D202").mkdir(parents=True)                           # folder, no record file
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd(["--notes", "D202", "--run-id", RUN, "--dry-run"], NoCalls())
        self.assertIn("D202", str(cm.exception))

    def test_more_than_one_record_stops(self):
        self.write_note("D202", "A", ext="csv")
        self.write_note("D202", "B")
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd(["--notes", "D202", "--run-id", RUN, "--dry-run"], NoCalls())
        self.assertIn("2 record files", str(cm.exception))

    def test_missing_folder_stops_before_any_call(self):
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd(["--notes", "D201", "D205", "--run-id", RUN, "--yes"], NoCalls())
        self.assertIn("D205", str(cm.exception))
        self.assertFalse(self.paths.outputs.exists())

    # ---- counting, the dry run, and the over-10 stop

    def test_dry_run_counts_and_makes_no_call(self):
        code, out = self.run_cmd(["--notes", "D201", "--run-id", RUN, "--dry-run"], NoCalls())
        self.assertEqual(code, 0)
        self.assertIn("New calls: 1", out)
        self.assertIn("no calls made", out)
        self.assertFalse(self.paths.outputs.exists())

    def test_mtsamples_dry_run_counts_twelve_and_needs_no_yes_for_a_plan(self):
        for n in range(201, 213):
            self.write_note(f"D{n}")
        code, out = self.run_cmd(["--mtsamples", "--run-id", RUN, "--dry-run"], NoCalls())
        self.assertEqual(code, 0)
        self.assertIn("Notes:     12", out)
        self.assertIn("New calls: 12", out)
        self.assertIn("needs a yes", out)                                       # a real run would stop here
        self.assertFalse(self.paths.outputs.exists())

    def test_over_ten_calls_stops_without_yes(self):
        for n in range(101, 112):                                                # 11 notes
            self.write_note(f"D{n}")
        code, out = self.run_cmd(["--notes", "D101-D111", "--run-id", RUN], NoCalls())
        self.assertEqual(code, 0)
        self.assertIn("--yes", out)
        self.assertIn("11 new calls", out)
        self.assertFalse(self.paths.outputs.exists())

    def test_over_ten_calls_goes_ahead_with_yes(self):
        for n in range(101, 112):
            self.write_note(f"D{n}")
        client = FakeClient([EMPTY] * 11)
        code, _ = self.run_cmd(["--notes", "D101-D111", "--run-id", RUN, "--yes"], client)
        self.assertEqual(code, 0)
        self.assertEqual(len(client.calls), 11)
        self.assertTrue(self.saved("compiled", "D111.json").exists())

    # ---- one note end to end (pretend reply -> Extract -> Check -> Compile)

    def test_one_record_end_to_end(self):
        client = FakeClient([GOOD])
        code, _ = self.run_cmd(["--notes", "D201", "--run-id", RUN], client)  # 1 call: no --yes needed
        self.assertEqual(code, 0)
        self.assertEqual(len(client.calls), 1)                                  # a passing note: one call only
        self.assertEqual(client.calls[0]["messages"][0]["content"], NOTE)     # the note text is what was sent
        self.assertTrue(self.saved("extracted", "D201_B.raw.txt").exists())
        self.assertFalse(self.saved("extracted", "D201_B.attempt2.json").exists())
        checked = json.loads(self.saved("checked", "D201_B.json").read_text(encoding="utf-8"))
        self.assertEqual(len(checked["facts"]), 2)
        report = json.loads(self.saved("checked", "check_report.json").read_text(encoding="utf-8"))
        self.assertTrue(report["records"]["D201_B"]["passed"])
        compiled = json.loads(self.saved("compiled", "D201.json").read_text(encoding="utf-8"))
        self.assertEqual(compile_step.validate(compiled), [])                   # passes shared/validate.py
        self.assertEqual(len(compiled["facts"]), 2)
        usage_lines = self.saved("extracted", "usage.csv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(usage_lines), 2)                                   # header + one call

    def test_bad_first_reply_gets_one_retry(self):
        client = FakeClient([BAD, GOOD])
        code, _ = self.run_cmd(["--notes", "D201", "--run-id", RUN], client)
        self.assertEqual(code, 0)
        self.assertEqual(len(client.calls), 2)                                  # the note + one retry
        retry = client.calls[1]["messages"]
        self.assertEqual([m["role"] for m in retry], ["user", "assistant", "user"])
        self.assertIn("quote not found in the record", retry[2]["content"])
        report = json.loads(self.saved("checked", "check_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["records"]["D201_B"]["attempt_kept"], 2)
        self.assertTrue(self.saved("compiled", "D201.json").exists())

    def test_restart_makes_no_calls(self):
        self.run_cmd(["--notes", "D201", "--run-id", RUN], FakeClient([GOOD]))
        code, out = self.run_cmd(["--notes", "D201", "--run-id", RUN], NoCalls())
        self.assertEqual(code, 0)
        self.assertIn("already finished", out)

    # ---- frozen files and the freeze tag

    def test_changed_frozen_file_stops_before_any_call(self):
        (self.root / "pipeline/tool/extract.py").write_text("changed\n", encoding="utf-8")
        for extra in ([], ["--dry-run"]):
            with self.subTest(dry_run=bool(extra)):
                with self.assertRaises(SystemExit) as cm:
                    self.run_cmd(["--notes", "D201", "--run-id", RUN, *extra], NoCalls())
                self.assertIn("pipeline/tool/extract.py", str(cm.exception))
        self.assertFalse(self.paths.outputs.exists())

    def test_no_freeze_tag_stops(self):
        subprocess.run(["git", "-C", str(self.root), "tag", "-d", "freeze"], check=True, capture_output=True)
        with self.assertRaises(SystemExit):
            self.run_cmd(["--notes", "D201", "--run-id", RUN, "--dry-run"])


class RealRepoTests(unittest.TestCase):
    def test_real_repo_frozen_files_match_freeze_tag(self):
        """Reads only: asks git whether the real frozen files still match the `freeze` tag."""
        self.assertEqual(live_run.frozen_state(), "frozen")


if __name__ == "__main__":
    unittest.main()
