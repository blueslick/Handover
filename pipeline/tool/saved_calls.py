"""Saved model calls (T20): save every extraction reply and its token usage, and replay it.

CLAUDE.md (Model calls) says every model reply is saved with its token usage, and that
the later steps (Check, omission check, compile, scoring) read saved replies and never
make new calls. This file is the only place a model call is saved or replayed.

How it works, in plain words:

  * call_or_replay() is what the extraction step (T19) calls for one hospital record.
    If that record already has a saved reply in this run, it hands back the saved reply
    and makes NO call. Otherwise it makes the call once, saves it, and hands it back.
  * load_saved() only reads a saved reply. It can never make a call, so the later steps
    use this one.
  * Saved files are never changed after they are written (shared/folders_and_names.md).
    A different prompt or model means a new run ID.
  * If the hospital record or the prompt file has changed since the reply was saved,
    replay stops with an error instead of quietly handing back an out-of-date reply.

Files, in outputs/extracted/<run_id>/ (names from shared/folders_and_names.md, plus the
two new ones marked *):

  P014_A.raw.txt              the model's exact reply text
  P014_A.call.json  *         everything about that call: model, prompt version, the
                              settings sent, token usage, stop reason, time, and a
                              fingerprint (sha256) of the record and prompt it was made from
  P014_A.attempt2.raw.txt     the one retry after a failed Check (attempt2.call.json too)
  usage.csv         *         one row per saved call, with tokens, written by the
                              `usage` command below

The schema-shaped P014_A.json (patient, facts, usage ...) is written by the extraction
step from the saved reply; it copies the usage from the .call.json file.

Commands (they print patient IDs and numbers only, never record or reply text, so they
are safe on held-out runs):

  python pipeline/tool/saved_calls.py usage <run_id>
      tokens per call and totals for one run; also writes usage.csv
  python pipeline/tool/saved_calls.py pending <run_id> P001 P002 ...
      how many NEW calls a run on those patients would make (3 per patient, minus the
      ones already saved). Use it before any run of more than 10 calls (CLAUDE.md).
"""
import argparse
import csv
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "outputs"
HOSPITALS = ("A", "B", "C")

# The same patterns the shared record format uses for IDs and file names.
PATIENT_RE = re.compile(r"^[PRD]\d{3}$")
RUN_RE = re.compile(r"^\d{8}-[A-Za-z0-9_.-]+$")


class SavedCallError(Exception):
    """Something about a saved call is wrong. The message says what, in plain words."""


@dataclass
class SavedCall:
    """One saved model reply: the exact text, the tokens it used, and the call details."""
    text: str
    usage: dict
    details: dict
    replayed: bool  # True = read from disk, no call made this time


# ---------------------------------------------------------------------------------
# File names. Every saved call lives at one fixed place, worked out from four things.
# ---------------------------------------------------------------------------------

def _check_ids(run_id, patient_id, hospital, attempt):
    """Stop early on a mistyped run ID, patient ID, hospital letter or attempt number."""
    if not RUN_RE.match(run_id or ""):
        raise SavedCallError(f"run ID {run_id!r} should look like 20261115-v1-sonnet-5-5")
    if not PATIENT_RE.match(patient_id or ""):
        raise SavedCallError(f"patient ID {patient_id!r} should look like P014")
    if hospital not in HOSPITALS:
        raise SavedCallError(f"hospital {hospital!r} should be A, B or C")
    if attempt not in (1, 2):
        raise SavedCallError("attempt must be 1, or 2 for the one retry (CLAUDE.md)")


def call_paths(run_id, patient_id, hospital, attempt=1, outputs=OUTPUTS):
    """The two files one call is saved in: (reply text, call details)."""
    _check_ids(run_id, patient_id, hospital, attempt)
    stem = f"{patient_id}_{hospital}" + ("" if attempt == 1 else ".attempt2")
    folder = Path(outputs) / "extracted" / run_id
    return folder / f"{stem}.raw.txt", folder / f"{stem}.call.json"


def is_saved(run_id, patient_id, hospital, attempt=1, outputs=OUTPUTS):
    """A call counts as saved only when BOTH files exist (details are written last)."""
    raw, details = call_paths(run_id, patient_id, hospital, attempt, outputs)
    return raw.exists() and details.exists()


def _sha256_file(path):
    """Fingerprint of a file, so we can tell later whether it has changed."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_new(path, text):
    """Write a file in one go (temp file, then rename), so a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------------
# Reading a saved call. This never makes a model call.
# ---------------------------------------------------------------------------------

def load_saved(run_id, patient_id, hospital, attempt=1, outputs=OUTPUTS,
               record_path=None, prompt_path=None):
    """Read one saved reply. Never calls the model.

    If record_path or prompt_path is given, also check that the file is unchanged
    since the reply was saved, and stop if it has changed.
    """
    raw, details_path = call_paths(run_id, patient_id, hospital, attempt, outputs)
    if not (raw.exists() and details_path.exists()):
        raise SavedCallError(
            f"no saved reply for {patient_id}_{hospital} (attempt {attempt}) in run {run_id}. "
            "This step reads saved replies only; run the extraction step first.")
    details = json.loads(details_path.read_text(encoding="utf-8"))
    text = raw.read_text(encoding="utf-8")

    # The reply text must be the one the details were saved with.
    if _sha256_text(text) != details.get("reply_sha256"):
        raise SavedCallError(
            f"{raw.name} no longer matches its saved details. Saved replies must never "
            "be edited (CLAUDE.md, Honest results).")
    for label, path, key in (("hospital record", record_path, "record_sha256"),
                             ("prompt", prompt_path, "prompt_sha256")):
        if path is not None and _sha256_file(path) != details.get(key):
            raise SavedCallError(
                f"the {label} {Path(path).name} has changed since {patient_id}_{hospital} "
                f"was saved in run {run_id}. Use a new run ID instead of replaying it.")
    return SavedCall(text=text, usage=details["usage"], details=details, replayed=True)


# ---------------------------------------------------------------------------------
# Making a call once and saving it, or replaying it if it is already saved.
# ---------------------------------------------------------------------------------

def reply_from_anthropic(message):
    """Pull the reply text, token usage and a few details out of an Anthropic API reply.

    Kept general (it reads attributes if they are there) so it does not depend on one
    exact version of the anthropic package.
    """
    text = "".join(getattr(block, "text", "") for block in message.content
                   if getattr(block, "type", None) == "text")
    u = message.usage
    usage = {"input_tokens": int(u.input_tokens), "output_tokens": int(u.output_tokens)}
    # Extra token counts the API may report (prompt caching, thinking); kept if present.
    for extra in ("cache_creation_input_tokens", "cache_read_input_tokens"):
        value = getattr(u, extra, None)
        if isinstance(value, int):
            usage[extra] = value
    extras = {
        "response_id": getattr(message, "id", None),
        "model_reported": getattr(message, "model", None),
        "stop_reason": getattr(message, "stop_reason", None),
    }
    return text, usage, extras


def _settings_without_text(request):
    """The settings that were sent, with the long prompt and record text swapped for
    fingerprints. The prompt and records are already in the repo, so the fingerprint is
    enough to prove which ones were used, and held-out text is not copied around."""
    settings = {}
    for key, value in request.items():
        if key in ("messages", "system"):
            settings[key + "_sha256"] = _sha256_text(json.dumps(value, sort_keys=True,
                                                                ensure_ascii=False))
        else:
            settings[key] = value
    return settings


def call_or_replay(run_id, patient_id, hospital, record_path, prompt_path, prompt_version,
                   request, send, attempt=1, outputs=OUTPUTS, read_reply=reply_from_anthropic):
    """Get the model's reply for one hospital record, making at most one call.

    run_id, patient_id, hospital, attempt: which call this is (decides the file names).
    record_path, prompt_path: the record and prompt files the request was built from.
    prompt_version: e.g. "v1"; must match the prompt file name (extract_v1.md).
    request: the settings sent to the API (model, max_tokens, messages, ...).
    send: the function that actually calls the API, e.g. client.messages.create.
          It is only used if nothing is saved yet.
    read_reply: turns the API reply into (text, usage, extras).
    """
    # 1. Already saved? Hand it back and make no call.
    if is_saved(run_id, patient_id, hospital, attempt, outputs):
        return load_saved(run_id, patient_id, hospital, attempt, outputs,
                          record_path=record_path, prompt_path=prompt_path)

    # 2. A retry is only allowed after attempt 1 has been saved.
    if attempt == 2 and not is_saved(run_id, patient_id, hospital, 1, outputs):
        raise SavedCallError(f"{patient_id}_{hospital}: attempt 1 must be saved before the retry")

    # 3. Basic checks before spending a call.
    if "model" not in request:
        raise SavedCallError("the request must name the exact pinned model ID")
    if f"extract_{prompt_version}" not in Path(prompt_path).stem:
        raise SavedCallError(f"prompt_version {prompt_version!r} does not match the prompt "
                             f"file {Path(prompt_path).name} (shared/folders_and_names.md)")
    record_sha = _sha256_file(record_path)
    prompt_sha = _sha256_file(prompt_path)

    # 4. Make the one call.
    started = datetime.now(timezone.utc)
    message = send(**request)
    text, usage, extras = read_reply(message)

    # 5. Save the exact reply first, then the details. The details file is what marks
    #    the call as saved, so a crash in between just means the call is made again.
    raw, details_path = call_paths(run_id, patient_id, hospital, attempt, outputs)
    details = {
        "run_id": run_id,
        "patient_id": patient_id,
        "hospital": hospital,
        "attempt": attempt,
        "source_file": Path(record_path).name,
        "model": request["model"],
        "prompt_version": prompt_version,
        "prompt_file": Path(prompt_path).name,
        "settings_sent": _settings_without_text(request),
        "usage": usage,
        **extras,
        "called_at_utc": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "record_sha256": record_sha,
        "prompt_sha256": prompt_sha,
        "reply_sha256": _sha256_text(text),
    }
    _write_new(raw, text)
    _write_new(details_path, json.dumps(details, indent=2, ensure_ascii=False) + "\n")
    return SavedCall(text=text, usage=usage, details=details, replayed=False)


# ---------------------------------------------------------------------------------
# Counting: new calls before a run, tokens after it.
# ---------------------------------------------------------------------------------

def count_new_calls(run_id, patient_ids, outputs=OUTPUTS):
    """How many first-attempt calls a run on these patients would still make.
    Retries are not counted: they only happen after a failed Check."""
    return sum(1 for p in patient_ids for h in HOSPITALS
               if not is_saved(run_id, p, h, 1, outputs))


USAGE_COLUMNS = ["patient_id", "hospital", "attempt", "model", "prompt_version",
                 "input_tokens", "output_tokens", "called_at_utc"]


def usage_rows(run_id, outputs=OUTPUTS):
    """One row per saved call in a run, sorted by patient, hospital and attempt."""
    folder = Path(outputs) / "extracted" / run_id
    rows = []
    for path in sorted(folder.glob("*.call.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        rows.append({col: (d["usage"].get(col) if col.endswith("_tokens") else d.get(col))
                     for col in USAGE_COLUMNS})
    rows.sort(key=lambda r: (r["patient_id"], r["hospital"], r["attempt"]))
    return rows


def write_usage_csv(run_id, outputs=OUTPUTS):
    """Write usage.csv for a run and return the rows. It is always rebuilt from the
    .call.json files, so it can't drift from them."""
    rows = usage_rows(run_id, outputs)
    if not rows:
        return rows  # nothing saved: don't create an empty folder or file
    path = Path(outputs) / "extracted" / run_id / "usage.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=USAGE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def _print_usage(run_id, outputs):
    rows = write_usage_csv(run_id, outputs)
    if not rows:
        print(f"No saved calls in run {run_id}.")
        return
    print(f"Run {run_id}: {len(rows)} saved calls")
    print(f"{'call':<16}{'model':<22}{'in':>8}{'out':>8}")
    for r in rows:
        name = f"{r['patient_id']}_{r['hospital']}" + ("" if r["attempt"] == 1 else " retry")
        print(f"{name:<16}{str(r['model']):<22}{r['input_tokens']:>8}{r['output_tokens']:>8}")
    tin = sum(r["input_tokens"] for r in rows)
    tout = sum(r["output_tokens"] for r in rows)
    retries = sum(1 for r in rows if r["attempt"] == 2)
    print(f"Total: {tin} input tokens, {tout} output tokens, {retries} retries.")
    print(f"Average per call: {tin / len(rows):.0f} in, {tout / len(rows):.0f} out.")
    print(f"Wrote {Path(outputs) / 'extracted' / run_id / 'usage.csv'}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Saved model calls (T20).")
    sub = parser.add_subparsers(dest="command", required=True)
    u = sub.add_parser("usage", help="tokens per call and totals for one run")
    u.add_argument("run_id")
    p = sub.add_parser("pending", help="how many new calls a run would make")
    p.add_argument("run_id")
    p.add_argument("patient_ids", nargs="+")
    args = parser.parse_args(argv)
    try:
        if args.command == "usage":
            _print_usage(args.run_id, OUTPUTS)
        else:
            n = count_new_calls(args.run_id, args.patient_ids)
            print(f"Run {args.run_id}: {n} new calls needed for {len(args.patient_ids)} "
                  f"patients ({3 * len(args.patient_ids) - n} already saved).")
    except SavedCallError as e:
        print(f"Stopped: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
