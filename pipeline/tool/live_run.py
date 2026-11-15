"""Live mode for the finals demo (T58): three hospital files in, one merged record out,
shown in the app running on this laptop.

    python pipeline/tool/live_run.py hospital_A.csv hospital_B.txt hospital_C.txt

What happens, in order:

  1. Checks the frozen tool is unchanged. If the `freeze` tag exists, the prompt, model
     settings, Check step, merge rules, brand table and drug list must match it exactly,
     or the command stops. If there is no tag yet, it says this is a practice run.
  2. Checks the three files: they exist, are plain text (.csv or .txt), are not empty or
     huge, and are not held-out or reserve records (CLAUDE.md, Held-out patients).
  3. Gives the live patient the next free ID from D901 to D999, so a live run never
     mixes with D001, the working patients or another live run.
  4. Says how many calls it will make (3, plus up to 3 retries) and WAITS for you to
     type yes. Nothing is sent before that.
  5. Copies the three files to pipeline/data/demo/<ID>/ (git-ignored) and runs the
     frozen tool through run_records.py, the one way this project calls the model:
     Extract (with the one retry), then Check. Every reply is saved in outputs/.
  6. Merges the three checked records with compile.py's six rules.
  7. Copies the merged record to app/data/live/ (git-ignored, so it is never pushed and
     never appears on the public Vercel link), starts the app on this laptop if it is not
     running, and opens the doctor screen for the new patient in the browser.

Other ways to run it:

    --demo        use the demo patient's own three records (D001) as the input, to rehearse
    --show D901   open an earlier live result again (no calls)
    --dry-run     do every check and say what would happen, but make no calls and copy nothing
    --no-open     don't start the app or open the browser

The API key is read from the git-ignored .env file, same as every other run. The app
itself never calls a model: it only reads the file this command leaves in app/data/live/.
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check  # noqa: E402
import compile as compile_step  # noqa: E402  (compile.py: the six merge rules)
import extract  # noqa: E402
import run_records  # noqa: E402

TOOL = Path(__file__).resolve().parent
REPO = TOOL.parent.parent
DATA = REPO / "pipeline" / "data"
DEMO_D001 = REPO / "pipeline" / "data" / "demo" / "D001"   # the --demo input
APP = REPO / "app"
APP_LIVE = APP / "data" / "live"
APP_URL = "http://localhost:3000"

# The frozen tool (T21 pick, T35 freeze). Not options: live mode always runs these.
FROZEN_MODEL = "claude-sonnet-5-5"
FROZEN_PROMPT = "v2"
# Files that decide what the tool does. After the freeze tag they must not differ from it.
FROZEN_FILES = [
    "pipeline/tool/prompts/extract_v2.md",
    "pipeline/tool/extract.py",
    "pipeline/tool/check.py",
    "pipeline/tool/compile.py",
    "shared/brand_to_generic.csv",
    "shared/drug_list.csv",
]

LIVE_IDS = [f"D{n}" for n in range(901, 1000)]
MAX_BYTES = 100_000          # a hospital record is a few KB; this keeps one call small
HOSPITALS = ("A", "B", "C")
# Where each hospital's copy is saved. run_records.py and the app expect these names.
COPY_NAME = {"A": "{pid}_A.csv", "B": "{pid}_B.txt", "C": "{pid}_C.txt"}
HIDDEN_NAME = re.compile(r"^(R\d{3}|P(0[2-9]\d|100))_[ABC]\.", re.IGNORECASE)


class Stop(SystemExit):
    """Stop with a plain message (no Python error text)."""

    def __init__(self, message):
        super().__init__(f"STOP: {message}")


# ---------------------------------------------------------------- 1. frozen tool

def freeze_tag_exists():
    return run_records.freeze_tag_exists()


def changed_since_freeze():
    """The frozen files that differ from the `freeze` tag (empty list = all unchanged)."""
    out = subprocess.run(["git", "-C", str(REPO), "diff", "--name-only", "freeze", "--", *FROZEN_FILES],
                         capture_output=True, text=True, encoding="utf-8")
    if out.returncode != 0:
        raise Stop("could not compare the tool with the `freeze` tag (git said: "
                   f"{out.stderr.strip() or 'no reason given'}).")
    return [line for line in out.stdout.splitlines() if line.strip()]


def frozen_state():
    """'frozen' when the tag exists and nothing changed, 'practice' when there's no tag yet."""
    if not freeze_tag_exists():
        return "practice"
    changed = changed_since_freeze()
    if changed:
        raise Stop("these files have changed since the freeze, so this would not be the frozen tool: "
                   + ", ".join(changed) + ". Put them back (git checkout freeze -- <file>) or ask the team.")
    return "frozen"


# ---------------------------------------------------------------- 2. input files

def check_input(path, hospital):
    """One input file: must be a small, non-empty text file that is not a held-out record."""
    path = Path(path).expanduser()
    if not path.is_file():
        raise Stop(f"Hospital {hospital} file '{path}' was not found.")
    parts = {p.lower() for p in path.resolve().parts}
    if "heldout" in parts or "reserve" in parts or HIDDEN_NAME.match(path.name):
        raise Stop(f"Hospital {hospital} file '{path.name}' is a held-out or reserve record. "
                   "Those are never run here (CLAUDE.md, Held-out patients).")
    if path.suffix.lower() not in (".csv", ".txt"):
        raise Stop(f"Hospital {hospital} file '{path.name}' must be a .csv or .txt file. "
                   "Save it as plain text first.")
    size = path.stat().st_size
    if size == 0:
        raise Stop(f"Hospital {hospital} file '{path.name}' is empty.")
    if size > MAX_BYTES:
        raise Stop(f"Hospital {hospital} file '{path.name}' is {size // 1000} KB; the limit is "
                   f"{MAX_BYTES // 1000} KB. A hospital record should be a few KB.")
    try:
        path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise Stop(f"Hospital {hospital} file '{path.name}' is not plain text (UTF-8).")
    return path


def demo_inputs():
    return [DEMO_D001 / "D001_A.csv", DEMO_D001 / "D001_B.txt", DEMO_D001 / "D001_C.txt"]


# ---------------------------------------------------------------- 3. live patient ID

def id_in_use(pid):
    return (DATA / "demo" / pid).exists() or any((extract.OUTPUTS / "extracted").glob(f"*-live-{pid}-*"))


def next_live_id():
    for pid in LIVE_IDS:
        if not id_in_use(pid):
            return pid
    raise Stop("all live IDs D901-D999 are used. Delete old live folders in pipeline/data/demo/ first.")


def make_run_id(pid, today=None):
    today = today or dt.date.today()
    return f"{today:%Y%m%d}-{FROZEN_PROMPT}-live-{pid}-{extract.short_model(FROZEN_MODEL)}"


def copy_inputs(pid, inputs):
    """Copy the three files into pipeline/data/demo/<pid>/ under the names the tool expects,
    plus a small note of where they came from."""
    folder = DATA / "demo" / pid
    folder.mkdir(parents=True, exist_ok=False)
    note = {"patient_id": pid, "made_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "inputs": {}}
    for hospital, src in zip(HOSPITALS, inputs):
        dst = folder / COPY_NAME[hospital].format(pid=pid)
        shutil.copyfile(src, dst)
        note["inputs"][hospital] = {"original_name": src.name, "saved_as": dst.name,
                                    "sha256": hashlib.sha256(dst.read_bytes()).hexdigest()}
    (folder / f"{pid}_live.json").write_text(json.dumps(note, indent=2, ensure_ascii=False) + "\n",
                                             encoding="utf-8")
    return note


# ---------------------------------------------------------------- 6. merge

def merge(pid, run_id):
    """Run compile.py's six rules on the checked records, write and validate the result."""
    checked = extract.OUTPUTS / "checked" / run_id
    paths = sorted(checked.glob(f"{pid}_[ABC].json"))
    if not paths:
        raise Stop("none of the three records could be read, so there is nothing to merge. "
                   f"The exact replies are saved in outputs/extracted/{run_id}/.")
    records = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    record = compile_step.compile_patient(pid, records, run_id=run_id)
    problems = compile_step.validate(record)
    if problems:
        raise Stop("the merged record failed the format check: " + "; ".join(problems[:3]))
    out = extract.OUTPUTS / "compiled" / run_id / f"{pid}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record, [p.stem.split("_")[1] for p in paths]


# ---------------------------------------------------------------- 7. hand to the app

def read_live_index():
    path = APP_LIVE / "index.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"format_version": "1.0",
            "note": "Live runs made on this laptop (T58). Git-ignored: never pushed, never on the public link.",
            "patients": []}


def publish_live(record, note, run_id, state, used):
    """Copy the merged record to app/data/live/ and add it to the live index."""
    pid = record["patient_id"]
    APP_LIVE.mkdir(parents=True, exist_ok=True)
    (APP_LIVE / f"{pid}_compiled.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                                                   encoding="utf-8")
    index = read_live_index()
    index["patients"] = [p for p in index["patients"] if p.get("patient_id") != pid]
    facts = record["facts"]
    index["patients"].append({
        "patient_id": pid,
        "run_id": run_id,
        "model": FROZEN_MODEL,
        "made_at": note["made_at"],
        "tool": "frozen" if state == "frozen" else "practice (no freeze tag yet)",
        "source_files": [note["inputs"][h]["original_name"] for h in HOSPITALS],
        "records_used": used,
        "facts": len(facts),
        "conflicts": len({f["conflict_group"] for f in facts if f["conflict_group"]}),
    })
    (APP_LIVE / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n",
                                         encoding="utf-8")


def app_is_running(url=APP_URL):
    try:
        with urllib.request.urlopen(url, timeout=3):
            return True
    except Exception:
        return False


def open_in_app(pid, opener=webbrowser.open, wait_seconds=120):
    """Start the app on this laptop if it isn't running, then open the doctor screen."""
    url = f"{APP_URL}/?id={pid}"
    if not app_is_running():
        npm = shutil.which("npm")
        if not npm:
            print(f"The app is not running and npm was not found. Start it yourself (cd app, npm run dev), "
                  f"then open {url}")
            return url
        if not (APP / "node_modules").is_dir():
            print("The app's packages are not installed yet. Run this once: cd app && npm install")
            print(f"Then start it (npm run dev) and open {url}")
            return url
        print("Starting the app on this laptop (npm run dev) ...")
        log = open(APP / ".next-live-dev.log", "w", encoding="utf-8")
        subprocess.Popen([npm, "run", "dev"], cwd=APP, stdout=log, stderr=subprocess.STDOUT,
                         start_new_session=True)
        for _ in range(wait_seconds):
            if app_is_running():
                break
            time.sleep(1)
        else:
            print(f"The app did not start within {wait_seconds} seconds. See app/.next-live-dev.log.")
            return url
    print(f"Opening {url}")
    opener(url)
    return url


# ---------------------------------------------------------------- the command

def show_earlier(pid, opener, no_open):
    pid = pid.upper()
    entry = next((p for p in read_live_index()["patients"] if p.get("patient_id") == pid), None)
    if entry is None or not (APP_LIVE / f"{pid}_compiled.json").exists():
        known = [p["patient_id"] for p in read_live_index()["patients"]]
        raise Stop(f"no live run {pid} on this laptop." + (f" Live runs here: {', '.join(known)}." if known else ""))
    print(f"{pid}: run {entry['run_id']}, made {entry['made_at']}, {entry['facts']} facts, "
          f"{entry['conflicts']} conflict(s). No calls made.")
    if not no_open:
        open_in_app(pid, opener)
    return 0


def main(argv=None, client=None, ask=input, opener=webbrowser.open):
    ap = argparse.ArgumentParser(description="Live mode (T58): run the frozen tool on three hospital "
                                             "files and open the result in the app on this laptop.")
    ap.add_argument("files", nargs="*", type=Path, help="the Hospital A, B and C files, in that order")
    ap.add_argument("--demo", action="store_true", help="use the demo patient D001's three records")
    ap.add_argument("--show", metavar="ID", help="open an earlier live run again (no calls)")
    ap.add_argument("--dry-run", action="store_true", help="check everything, make no calls, copy nothing")
    ap.add_argument("--no-open", action="store_true", help="don't start the app or open the browser")
    args = ap.parse_args(argv)

    if args.show:
        return show_earlier(args.show, opener, args.no_open)

    # 1. The frozen tool.
    state = frozen_state()

    # 2. The three input files.
    if args.demo and args.files:
        raise Stop("give either three files or --demo, not both.")
    raw = demo_inputs() if args.demo else args.files
    if len(raw) != 3:
        raise Stop(f"give exactly three files (Hospital A, B, C), not {len(raw)}. "
                   "Example: python pipeline/tool/live_run.py a.csv b.txt c.txt")
    inputs = [check_input(p, h) for p, h in zip(raw, HOSPITALS)]
    if len({hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}) < 3:
        print("Note: two of the files are identical.")

    # 3. A new live patient ID and run ID.
    pid = next_live_id()
    run_id = make_run_id(pid)

    # 4. Say what will happen, then wait for a yes.
    print("Live run (T58)")
    if state == "frozen":
        print("Tool:      frozen tool (matches the `freeze` tag)")
    else:
        print("Tool:      PRACTICE RUN - there is no `freeze` tag yet, so this uses the current files")
    print(f"Model:     {FROZEN_MODEL}    Prompt: extract_{FROZEN_PROMPT}.md")
    for h, p in zip(HOSPITALS, inputs):
        print(f"Hospital {h}: {p.name} ({p.stat().st_size:,} bytes)")
    print(f"Patient:   {pid}    Run ID: {run_id}")
    print("Calls:     3 (one per hospital), plus up to 3 retries if a reading fails the Check step. "
          "About 3 US cents in the working runs.")
    if args.dry_run:
        print("Dry run: no calls made, nothing copied.")
        return 0
    answer = ask("Type yes to send these three records to Claude now: ").strip().lower()
    if answer not in ("yes", "y"):
        print("Not sent. Nothing was copied and no calls were made.")
        return 0

    # 5. Copy, then Extract (+ one retry) and Check through run_records.py.
    note = copy_inputs(pid, inputs)
    print()
    code = run_records.main(["--model", FROZEN_MODEL, "--prompt", FROZEN_PROMPT, "--patients", pid,
                             "--run-id", run_id, "--no-compile"], client=client)
    if code:
        raise Stop("the run did not finish; see the lines above. Saved replies are kept.")

    # 6. Merge.
    print("\n--- Merge step ---")
    record, used = merge(pid, run_id)
    facts = record["facts"]
    conflicts = len({f["conflict_group"] for f in facts if f["conflict_group"]})
    print(f"{pid}: {len(facts)} facts, {conflicts} conflict(s), from hospitals {', '.join(used)}")
    if len(used) < 3:
        print(f"Warning: only {len(used)} of 3 records could be used; the merged record says which.")

    # 7. Hand to the app on this laptop.
    publish_live(record, note, run_id, state, used)
    print(f"Saved for the app: app/data/live/{pid}_compiled.json (stays on this laptop)")
    if not args.no_open:
        open_in_app(pid, opener)
    print(f"To open it again later with no calls: python pipeline/tool/live_run.py --show {pid}")
    print("Backup if the internet fails: the saved demo patient, http://localhost:3000/?id=D001")
    return 0


if __name__ == "__main__":
    sys.exit(main())
