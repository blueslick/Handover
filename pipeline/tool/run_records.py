"""Run the tool on many records at once (for T21, T31 and the held-out run T36).

For every patient asked for, and each of its three hospital records (A, B, C):

  1. Extract: one model call per record, through extract.extract_with_retry(), which
     goes through saved_calls.py (T20). A record that already has a saved reply in this
     run is replayed, with no new call, so a run that stopped halfway can just be
     started again with the same command.
  2. The one retry: if the Check step (check.py) fails the first try, the model gets
     ONE more call with the list of problems. The try with fewer problems is kept.
     Never a third call (CLAUDE.md, Model calls).
  3. Check: check.run() writes outputs/checked/<run_id>/ from the saved files.
  4. Compile: compile.py writes one merged record per patient to outputs/compiled/<run_id>/.
  5. Tokens: saved_calls.py writes outputs/extracted/<run_id>/usage.csv.

Safety rules built in:

  * Before making any calls it prints how many new calls the run needs. Over 10, it
    stops and asks you to run it again with --yes (CLAUDE.md: tell the person and wait).
  * Held-out and reserve patients are refused unless you pass --heldout AND the
    `freeze` tag exists (CLAUDE.md, Held-out patients). For them only IDs and counts
    are printed, never what a record or reply says.
  * If the API key, the model name or a setting is refused, the run stops at once.
    If the connection drops or the API is busy, it waits 30 seconds and tries that
    record once more (nothing was saved, so this is not the model "retry"); if it
    fails again, the run stops. Run the same command later to carry on.

Examples:

    # T21: compare the two models on 5 working patients (15 calls each, plus retries)
    python pipeline/tool/run_records.py --model claude-sonnet-5-5 --patients P001 P002 P003 P004 P005
    python pipeline/tool/run_records.py --model claude-haiku-5-5 --patients P001 P002 P003 P004 P005

    # T31: all 20 working patients
    python pipeline/tool/run_records.py --model claude-sonnet-5-5 --working

    --dry-run     show the records and the call count, make no calls (no key needed)
    --yes         go ahead with a run of more than 10 calls
    --prompt v1   which prompt file (default v1)
    --run-id ID   default <YYYYMMDD>-<prompt>-<model short name>, same as extract.py
"""
import argparse
import datetime as dt
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check  # noqa: E402
import extract  # noqa: E402
import saved_calls  # noqa: E402

TOOL = Path(__file__).resolve().parent
REPO = TOOL.parent.parent
DATA = REPO / "pipeline" / "data"
SPLIT = DATA / "split"
ASK_ABOVE = 10   # CLAUDE.md: more than 10 calls needs a yes

# Errors that mean "stop the whole run": retrying won't help.
STOP_ERRORS = {
    "AuthenticationError": "the API key was rejected. Check the key in .env.",
    "PermissionDeniedError": "the key is not allowed to use this model.",
    "NotFoundError": "the model name was not found.",
    "BadRequestError": "the API refused the request (often a setting or the JSON shape).",
}
# Errors that are usually passing: wait, then try the same record once more.
WAIT_ERRORS = {"RateLimitError", "APIConnectionError", "APITimeoutError",
               "InternalServerError", "OverloadedError"}
WAIT_SECONDS = 30


def is_hidden(patient_id):
    """Held-out (P021-P100) and reserve (R...) patients: counts only, never contents."""
    return check.is_hidden(patient_id)


def freeze_tag_exists():
    out = subprocess.run(["git", "-C", str(REPO), "tag", "-l", "freeze"],
                         capture_output=True, text=True, encoding="utf-8")
    return out.stdout.strip() == "freeze"


def read_ids(name):
    path = SPLIT / name
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def patient_folder(patient_id):
    """Where a patient's three records live."""
    if patient_id.startswith("D"):
        return DATA / "demo" / patient_id
    if patient_id.startswith("R"):
        return DATA / "reserve" / patient_id
    return DATA / ("heldout" if is_hidden(patient_id) else "working") / patient_id


def record_paths(patient_id):
    """The three hospital records for one patient: A is a CSV, B and C are text."""
    folder = patient_folder(patient_id)
    paths = [folder / f"{patient_id}_A.csv", folder / f"{patient_id}_B.txt", folder / f"{patient_id}_C.txt"]
    missing = [p.name for p in paths if not p.exists()]
    if missing:
        raise SystemExit(f"STOP: {patient_id} is missing {', '.join(missing)} in "
                         f"{folder.relative_to(REPO)}.")
    return paths


def choose_patients(args):
    if args.patients:
        ids = list(dict.fromkeys(args.patients))   # keep order, drop repeats
    elif args.working:
        ids = [f"P{n:03d}" for n in range(1, 21)]
    else:
        ids = [f"P{n:03d}" for n in range(21, 101)] + [f"R{n:03d}" for n in range(1, 81)]
    for pid in ids:
        if not saved_calls.PATIENT_RE.match(pid):
            raise SystemExit(f"STOP: '{pid}' is not a patient ID like P001, R001 or D001.")
    hidden = [p for p in ids if is_hidden(p)]
    if hidden and not args.heldout:
        raise SystemExit(f"STOP: {len(hidden)} of these are held-out or reserve patients. They run only "
                         "once, after the freeze, with --heldout (CLAUDE.md, Held-out patients).")
    if hidden and not freeze_tag_exists():
        raise SystemExit("STOP: there is no `freeze` tag yet, so held-out patients can't be run "
                         "(CLAUDE.md, Held-out patients; T35 makes the freeze).")
    return ids


def make_client():
    key = extract.load_key()
    if not key:
        raise SystemExit("STOP: no API key. Put ANTHROPIC_API_KEY=... in the .env file at the repo root.")
    import anthropic
    return anthropic.Anthropic(api_key=key)


def run_one(record, args, run_id, client):
    """One record: extract, check, retry once if needed. Waits and tries again once if the
    API was busy or the connection dropped (nothing was saved in that case)."""
    for try_number in (1, 2):
        try:
            return extract.extract_with_retry(model=args.model, record_path=record,
                                              prompt_version=args.prompt, run_id=run_id,
                                              client=client)
        except Exception as e:
            name = type(e).__name__
            if name in STOP_ERRORS:
                raise SystemExit(f"STOPPED at {record.stem}: {STOP_ERRORS[name]} "
                                 "Everything before this record is saved.")
            if name in WAIT_ERRORS and try_number == 1:
                print(f"  {record.stem}: API busy or connection dropped ({name}). "
                      f"Waiting {WAIT_SECONDS} seconds, then trying this record once more.")
                time.sleep(WAIT_SECONDS)
                continue
            if name in WAIT_ERRORS:
                raise SystemExit(f"STOPPED at {record.stem}: the API is still not answering ({name}). "
                                 "Everything before this record is saved; run the same command later.")
            raise


def main(argv=None, client=None):
    ap = argparse.ArgumentParser(description="Run Extract (with the one retry), Check and Compile "
                                             "on many records.")
    ap.add_argument("--model", required=True, choices=sorted(extract.THINKING))
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--patients", nargs="+", help="patient IDs, e.g. P001 P002")
    group.add_argument("--working", action="store_true", help="all 20 working patients (P001-P020)")
    group.add_argument("--all-heldout", action="store_true",
                       help="all 160 held-out patients (P021-P100, R001-R080); needs --heldout and the freeze tag")
    ap.add_argument("--heldout", action="store_true", help="allow held-out and reserve patients (after the freeze only)")
    ap.add_argument("--prompt", default="v1")
    ap.add_argument("--run-id")
    ap.add_argument("--yes", action="store_true", help=f"go ahead with more than {ASK_ABOVE} calls")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-compile", action="store_true", help="stop after Check")
    args = ap.parse_args(argv)

    if not (extract.PROMPTS / f"extract_{args.prompt}.md").exists():
        raise SystemExit(f"STOP: no prompt file pipeline/tool/prompts/extract_{args.prompt}.md.")
    ids = choose_patients(args)
    records = [r for pid in ids for r in record_paths(pid)]
    run_id = args.run_id or f"{dt.date.today():%Y%m%d}-{args.prompt}-{extract.short_model(args.model)}"

    # Count before spending anything.
    new_calls = saved_calls.count_new_calls(run_id, ids, extract.OUTPUTS)
    n_hidden = sum(is_hidden(p) for p in ids)
    print(f"Run ID:   {run_id}")
    print(f"Model:    {args.model}    Prompt: extract_{args.prompt}.md")
    print(f"Patients: {len(ids)}" + (f" ({n_hidden} held-out/reserve, contents not shown)" if n_hidden else
                                     f" ({' '.join(ids)})"))
    print(f"Records:  {len(records)}    already saved: {len(records) - new_calls}")
    print(f"New calls: {new_calls}, plus up to {new_calls} retries (only for records that fail the Check step)")

    if args.dry_run:
        print("Dry run: no calls made.")
        return 0
    if new_calls > ASK_ABOVE and not args.yes:
        print(f"This is more than {ASK_ABOVE} calls, so it needs a yes (CLAUDE.md). "
              "If that's fine, run the same command again with --yes added.")
        return 0

    if client is None and new_calls > 0:
        client = make_client()
    elif client is None:
        client = extract.SimpleNamespace(messages=extract.SimpleNamespace(create=extract._no_call))

    # Extract + one retry, record by record.
    totals = {"calls": 0, "retried": 0, "kept_retry": 0, "still_failing": 0, "unreadable": []}
    for i, record in enumerate(records, 1):
        pid = record.stem.split("_")[0]
        try:
            r = run_one(record, args, run_id, client)
        except extract.ExtractFailed as e:
            totals["unreadable"].append(record.stem)
            print(f"[{i}/{len(records)}] {record.stem}: could not be read"
                  + ("" if is_hidden(pid) else f" ({e})"))
            continue
        totals["calls"] += r["calls"]
        totals["retried"] += r["retried"]
        totals["kept_retry"] += r["attempt_kept"] == 2
        totals["still_failing"] += r["problems_left"] > 0
        if is_hidden(pid):
            print(f"[{i}/{len(records)}] done")
        else:
            note = "passed" if not r["problems_left"] else f"{r['problems_left']} problems left"
            if r["retried"]:
                note += f", retried, kept attempt {r['attempt_kept']}"
            print(f"[{i}/{len(records)}] {record.stem}: {r['facts']} facts, {note}, "
                  f"{r['calls']} new calls")

    print(f"\nExtract done: {totals['calls']} new calls, {totals['retried']} records retried "
          f"({totals['kept_retry']} kept the retry), {totals['still_failing']} still have problems "
          f"(their facts are kept with the 'unverified' flag).")
    if totals["unreadable"]:
        print(f"Could not be read: {len(totals['unreadable'])} records. Their exact replies are saved; "
              "send this output to the team.")

    # Check: writes outputs/checked/<run_id>/ from the saved files (no calls).
    print("\n--- Check step ---")
    check.run(run_id, ids)

    # Compile: one merged record per patient (no calls).
    if not args.no_compile:
        print("\n--- Compile step ---")
        subprocess.run([sys.executable, str(TOOL / "compile.py"), "--run", run_id, "--patients", *ids],
                       cwd=REPO)

    # Tokens per call, for T21.
    print("\n--- Tokens ---")
    rows = saved_calls.write_usage_csv(run_id, extract.OUTPUTS)
    if rows:
        tin = sum(r["input_tokens"] for r in rows)
        tout = sum(r["output_tokens"] for r in rows)
        print(f"{len(rows)} saved calls in this run: {tin} input tokens, {tout} output tokens "
              f"(average {tin / len(rows):.0f} in, {tout / len(rows):.0f} out). "
              f"Per call: outputs/extracted/{run_id}/usage.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
