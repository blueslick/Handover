"""Run the frozen tool on single notes: one note = one "patient" with one record file.

Used for the T43 MTSamples notes (D201-D212) and, later, the T40 trap notes (D101-D140).
Each note is one folder with exactly one hospital record file in it:

    pipeline/data/demo/D201/D201_B.txt      the full note text (any letter A, B or C works)

Steps for each note, reusing the same functions as run_records.py:

  1. Extract: one model call through run_records.run_one() -> extract.extract_with_retry()
     -> saved_calls.py. The reply is saved; a note with a saved reply is replayed, no call.
  2. The one retry: only if the Check step fails the first try. Never a third call.
  3. Check: check.run() on the saved files of these notes (no calls).
  4. Compile: compile_patient() and validate() from compile.py, the same functions its
     command line uses, on the one checked record (no calls).
  5. Tokens: saved_calls.write_usage_csv() rebuilds usage.csv for the run (no calls).

Output goes to outputs/extracted/<run-id>/, outputs/checked/<run-id>/ and
outputs/compiled/<run-id>/. Nothing is published (no store.py, no app/data/).

Rules built in:

  * Only D101-D140 (trap notes) and D201-D212 (MTSamples notes). Any other ID stops the run.
  * Exactly one record file per note folder. 0 or more than 1 stops the run.
  * Model and prompt come from live_run.FROZEN_MODEL and live_run.FROZEN_PROMPT. There are
    no --model or --prompt options.
  * live_run.frozen_state() runs before any call. It stops if a frozen file has changed
    since the `freeze` tag, and it also stops if there is no tag yet.
  * It counts the new calls first. Over 10 new calls, it stops unless you pass --yes
    (CLAUDE.md). --dry-run prints the notes and the count and makes no calls.
  * Restart: run the same command again. Saved replies are replayed, finished notes are
    skipped.

Examples:

    # One note, plan only (no calls, no key needed):
    python pipeline/tool/run_single_notes.py --notes D201 --run-id 20261115-v2-mtsamples-sonnet-5-5 --dry-run

    # All 12 MTSamples notes, plan only. It will ask for --yes before any real call:
    python pipeline/tool/run_single_notes.py --mtsamples --run-id 20261115-v2-mtsamples-sonnet-5-5 --dry-run
"""
import argparse
import json
import re
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check  # noqa: E402  (Check step: check.run, and the one retry's rule)
import compile as compile_step  # noqa: E402  (Compile step: compile_patient and validate)
import extract  # noqa: E402  (Extract step: the prompt folder, OUTPUTS, ExtractFailed)
import live_run  # noqa: E402  (FROZEN_MODEL, FROZEN_PROMPT, frozen_state: the frozen settings)
import run_records  # noqa: E402  (run_one: Extract with the one retry; make_client)
import saved_calls  # noqa: E402  (saved replies, is_saved, usage.csv)

TOOL = Path(__file__).resolve().parent
REPO = TOOL.parent.parent

MTSAMPLES_IDS = [f"D{n}" for n in range(201, 213)]   # T43: D201-D212 = M001-M012
TRAP_IDS = [f"D{n}" for n in range(101, 141)]        # T40: D101-D140
ALLOWED_IDS = set(MTSAMPLES_IDS) | set(TRAP_IDS)
ASK_ABOVE = 10                                       # CLAUDE.md: more than 10 calls needs a yes
RECORD_FILE = re.compile(r"^(D\d{3})_([ABC])\.(csv|txt)$")


@dataclass
class Paths:
    """Where things are. The real run uses the repo; the tests use a temporary copy."""
    data: Path      # pipeline/data (note folders live in data/demo/)
    outputs: Path   # outputs/ (the real run writes here)

    @property
    def demo(self):
        """The folder that holds the note folders (D201/, D202/ ...)."""
        return self.data / "demo"


def default_paths():
    """The real locations in this repo."""
    return Paths(data=REPO / "pipeline" / "data", outputs=REPO / "outputs")


def show(path):
    """A path relative to the repo when it is inside it, for printing."""
    try:
        return str(Path(path).relative_to(REPO))
    except ValueError:
        return str(path)


def parse_ids(tokens):
    """'D201 D203' or 'D201-D212' -> ['D201', 'D203'] or ['D201', ..., 'D212'], in order, no repeats.
    Only the allowed note IDs pass. Anything else stops the run before any work is done."""
    ids = []
    for token in tokens:
        token = token.strip().upper()
        m = re.fullmatch(r"(D\d{3})-(D\d{3})", token)
        if m:
            # A range such as D201-D212: expand it inclusively.
            lo, hi = int(m.group(1)[1:]), int(m.group(2)[1:])
            if hi < lo:
                raise SystemExit(f"STOP: the range {token} runs backwards. Nothing was run.")
            ids.extend(f"D{n:03d}" for n in range(lo, hi + 1))
        else:
            ids.append(token)
    bad = [pid for pid in ids if pid not in ALLOWED_IDS]
    if bad:
        raise SystemExit(f"STOP: {', '.join(bad[:5])} not allowed. This runner takes only D101-D140 "
                         "(trap notes) and D201-D212 (MTSamples notes). D001, D9xx, P and R patients "
                         "are never run here. Nothing was run.")
    return list(dict.fromkeys(ids))


def select_ids(args):
    """The notes asked for: --notes IDs, plus --mtsamples (D201-D212) and --traps (D101-D140)."""
    ids = parse_ids(args.notes or [])
    if args.mtsamples:
        ids += MTSAMPLES_IDS
    if args.traps:
        ids += TRAP_IDS
    ids = list(dict.fromkeys(ids))
    if not ids:
        raise SystemExit("STOP: say which notes to run: --notes D201 D202 ..., --mtsamples or --traps.")
    return ids


def find_record(paths, pid):
    """The one record file in a note's folder. Returns (path, letter). Stops on 0 or more than 1."""
    folder = paths.demo / pid
    if not folder.is_dir():
        raise SystemExit(f"STOP: no folder for {pid} at {show(folder)}. Nothing was run.")
    found = []
    for path in sorted(folder.iterdir()):
        m = RECORD_FILE.match(path.name)
        if m and m.group(1) == pid:
            found.append((path, m.group(2)))
    if not found:
        raise SystemExit(f"STOP: {pid} has no record file in {show(folder)}. Expected one file named "
                         f"{pid}_A.csv, {pid}_B.txt or {pid}_C.txt. Nothing was run.")
    if len(found) > 1:
        names = ", ".join(p.name for p, _ in found)
        raise SystemExit(f"STOP: {pid} has {len(found)} record files ({names}). Exactly one is allowed. "
                         "Nothing was run.")
    path, letter = found[0]
    try:
        path.read_text(encoding="utf-8")                  # every record is read as UTF-8
    except UnicodeDecodeError:
        raise SystemExit(f"STOP: {path.name} is not UTF-8 text. Nothing was run.")
    if path.stat().st_size == 0:
        raise SystemExit(f"STOP: {path.name} is empty. Nothing was run.")
    return path, letter


def is_done(root, run_id, pid, letter):
    """A note is finished when its checked and compiled files are both saved in this run."""
    return ((root / "checked" / run_id / f"{pid}_{letter}.json").exists()
            and (root / "compiled" / run_id / f"{pid}.json").exists())


@contextmanager
def folders_here(root, data):
    """extract.py and check.py read their output and data folders from module settings.
    Point them at `root` and `data` for this run, then put the old settings back."""
    old = (extract.OUTPUTS, check.OUTPUTS, check.DATA)
    extract.OUTPUTS, check.OUTPUTS, check.DATA = root, root, data
    try:
        yield
    finally:
        extract.OUTPUTS, check.OUTPUTS, check.DATA = old


class LazyClient:
    """Builds the real API client only when the first real call is about to be made. A restart
    that needs no call therefore does not need the API key."""

    def __init__(self, make):
        self._make = make
        self._real = None
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        if self._real is None:
            self._real = self._make()
        return self._real.messages.create(**kw)


def compile_note(root, run_id, pid, letter):
    """Step 4 for one note: its checked record -> outputs/compiled/<run>/<ID>.json. Returns a
    plain-words problem, or None when the compiled file is saved and passes the format check."""
    out = root / "compiled" / run_id / f"{pid}.json"
    if out.exists():
        return None                       # already saved in this run: saved files are never overwritten
    checked = root / "checked" / run_id / f"{pid}_{letter}.json"
    if not checked.exists():
        return "its note could not be read, so there is nothing to compile"
    record = compile_step.compile_patient(pid, [json.loads(checked.read_text(encoding="utf-8"))],
                                          run_id=run_id)
    problems = compile_step.validate(record)
    if problems:
        return "the compiled record failed the format check: " + "; ".join(problems[:3])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return None


def process(paths, run_id, items, client):
    """Steps 1 to 5 for every note in `items` (a list of (ID, record path, letter)).
    Reads and writes only under paths.outputs."""
    root = paths.outputs
    args = SimpleNamespace(model=live_run.FROZEN_MODEL, prompt=live_run.FROZEN_PROMPT)
    calls, retried, unreadable = 0, 0, []
    with folders_here(root, paths.data):
        # Step 1: Extract, with the one retry (run_records.run_one -> extract.extract_with_retry).
        for i, (pid, record, letter) in enumerate(items, 1):
            if is_done(root, run_id, pid, letter):
                print(f"[{i}/{len(items)}] {pid}: already finished in this run. No call.")
                continue
            try:
                r = run_records.run_one(record, args, run_id, client)
            except extract.ExtractFailed as e:
                unreadable.append(pid)
                print(f"[{i}/{len(items)}] {pid}: could not be read into facts ({e}). Its exact reply is saved.")
                continue
            calls += r["calls"]
            retried += int(r["retried"])
            state = ("passed Check" if not r["problems_left"]
                     else f"{r['problems_left']} problem(s) left, kept flagged 'unverified'")
            if r["retried"]:
                state += f", retried, kept attempt {r['attempt_kept']}"
            print(f"[{i}/{len(items)}] {pid}: {r['facts']} facts, {state}, {r['calls']} new call(s)")

        # Step 2: Check, on the saved files of every note that has an extraction (no calls).
        # All of them go in one call, so check_report.json covers the whole run.
        print("\n--- Check step ---")
        have = [(pid, letter) for pid, _, letter in items
                if (root / "extracted" / run_id / f"{pid}_{letter}.json").exists()]
        if have:
            check.run(run_id, [pid for pid, _ in have])
        else:
            print("No extracted notes to check.")

        # Step 3: Compile, one note at a time (no calls).
        print("\n--- Compile step ---")
        failed = []
        for pid, _, letter in items:
            problem = compile_note(root, run_id, pid, letter)
            if problem:
                failed.append(f"{pid}: {problem}")
        compiled = sum((root / "compiled" / run_id / f"{pid}.json").exists() for pid, _, _ in items)
        print(f"Compiled {compiled} of {len(items)} notes into {show(root / 'compiled' / run_id)}")
        for line in failed:
            print("FAILED", line)

        # Step 5: usage.csv for the run (rebuilt from the saved .call.json files).
        rows = saved_calls.write_usage_csv(run_id, root)
        if rows:
            tin = sum(r["input_tokens"] for r in rows)
            tout = sum(r["output_tokens"] for r in rows)
            print(f"\n{len(rows)} saved calls in this run: {tin} input tokens, {tout} output tokens. "
                  f"Per call: {show(root / 'extracted' / run_id / 'usage.csv')}")

    print(f"\nNew model calls this run: {calls} (notes that needed the one retry: {retried}). "
          f"Could not be read: {len(unreadable)}.")
    return {"calls": calls, "retried": retried, "unreadable": unreadable, "failed": failed}


def main(argv=None, client=None, paths=None):
    """The command. Returns 0 when the run finished (or stopped on purpose for a yes),
    1 when some notes could not be read or compiled. Problems that must stop the run raise SystemExit."""
    paths = paths or default_paths()
    ap = argparse.ArgumentParser(description="Run the frozen tool on single notes (one note = one patient).")
    ap.add_argument("--notes", nargs="+", metavar="ID",
                    help="note IDs, e.g. D201 D202 or D201-D212 (only D101-D140 and D201-D212)")
    ap.add_argument("--mtsamples", action="store_true", help="all 12 MTSamples notes, D201-D212")
    ap.add_argument("--traps", action="store_true", help="all 40 trap notes, D101-D140")
    ap.add_argument("--run-id", required=True,
                    help="run ID, e.g. 20261115-v2-mtsamples-sonnet-5-5 (required; no default)")
    ap.add_argument("--yes", action="store_true", help="go ahead when the run has more than 10 new calls")
    ap.add_argument("--dry-run", action="store_true", help="print the notes and the call count; no calls")
    args = ap.parse_args(argv)

    # The run ID must look right and must not be a held-out run (CLAUDE.md, Held-out patients).
    if not saved_calls.RUN_RE.match(args.run_id) or "heldout" in args.run_id.lower():
        raise SystemExit(f"STOP: run ID '{args.run_id}' should look like 20261115-v2-mtsamples-sonnet-5-5 "
                         "and must not be a held-out run. Nothing was run.")

    # Checks before anything is counted or sent.
    ids = select_ids(args)
    state = live_run.frozen_state()          # stops if a frozen file changed; "practice" if no tag
    if state != "frozen":
        raise SystemExit("STOP: there is no `freeze` tag, so the frozen tool cannot be checked. "
                         "Nothing was run.")
    items = []
    for pid in ids:
        record, letter = find_record(paths, pid)
        items.append((pid, record, letter))

    # Count first (CLAUDE.md: say how many calls, then wait for a yes).
    new = [(pid, rec, letter) for pid, rec, letter in items
           if not saved_calls.is_saved(args.run_id, pid, letter, 1, paths.outputs)]
    print(f"Run ID:    {args.run_id}")
    print(f"Model:     {live_run.FROZEN_MODEL}    Prompt: extract_{live_run.FROZEN_PROMPT}.md    "
          "Tool: frozen (matches the freeze tag)")
    print(f"Notes:     {len(items)}: " + ", ".join(f"{pid} ({rec.name})" for pid, rec, _ in items))
    print(f"Already saved: {len(items) - len(new)}.   New calls: {len(new)}, plus up to {len(new)} "
          "retries (only for notes that fail the Check step).")

    if args.dry_run:
        print("Dry run: no calls made, nothing written.")
        if len(new) > ASK_ABOVE and not args.yes:
            # Say here what a real run would do, so the dry run shows the stop too.
            print(f"A real run would stop at this point: {len(new)} new calls is more than {ASK_ABOVE}, "
                  "so it needs a yes (--yes) from Daniel (CLAUDE.md). Not added here.")
        return 0
    if len(new) > ASK_ABOVE and not args.yes:
        print(f"This run would make {len(new)} new calls, which is more than {ASK_ABOVE}, so it needs a yes "
              "(CLAUDE.md). Run the same command again with --yes added. No calls were made; nothing was written.")
        return 0

    # The real run. The API key is read only when the first real call is made.
    if client is None:
        client = LazyClient(run_records.make_client)
    summary = process(paths, args.run_id, items, client)
    return 1 if (summary["unreadable"] or summary["failed"]) else 0


if __name__ == "__main__":
    sys.exit(main())
