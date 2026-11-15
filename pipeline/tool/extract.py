"""Extract step (T19): send ONE hospital record to the model and save its facts.

Section 4 of docs/Handover_Pipeline_and_Frontend_Plan.md. This is the only step
that calls the model. Check, compile and scoring read the files it saves.

What it does, in order:

  1. Reads one record file (P001_A.csv, D001_C.txt ...) and the prompt
     pipeline/tool/prompts/extract_<version>.md.
  2. Sends them to the model in ONE call, asking for a fixed JSON shape
     (output_config), so the reply is always valid JSON. The call goes through
     saved_calls.call_or_replay() (T20): if this record already has a saved reply in
     the run, that reply is used and NO call is made.
  3. saved_calls.py saves the model's exact reply (<record>.raw.txt) and the call
     details with token usage (<record>.call.json) in outputs/extracted/<run_id>/.
  4. Wraps the facts in the extracted record shape (shared/schema/extracted.schema.json),
     with the token counts from the API's `usage` field, and saves it as
     outputs/extracted/<run_id>/<record>.json.
  5. Runs shared/validate.py on it and prints what it found.

The only things this file adds to the model's facts are two flags a rule says must be
there, so the file is valid: `missing_dose` on a current medicine with no dose, and
`unknown_name` when the model gave no generic name. Everything else is the model's own
answer. Brand conversion and quote checks are the Check step (T22).

Settings (agreed in T56): Claude 5.5 models refuse `temperature` and refuse
thinking "disabled" (found in T08). So: temperature, top_p and top_k are not sent
(default sampling), thinking is at the lowest setting each model accepts, and the
reply must follow a fixed JSON shape. The saved reply is what makes later steps
repeatable.

Run it (one call, one record):

    python pipeline/tool/extract.py --model claude-sonnet-5-5 --record pipeline/data/demo/D001/D001_C.txt

    --prompt v1          which prompt file to use (default v1)
    --run-id <id>        default <YYYYMMDD>-<prompt>-<model short name>
    --dry-run            print what would be sent, make no call (no key needed)

Plain lists (T66, results-table row 4): a prompt whose version ends in "-plain"
(extract_v2-plain.md) asks for the same facts with NO status label. The reply shape then
has no status field, and this file saves every such fact as "current", which is the
plan's rule for scoring a list with no labels. That row never goes through the Check
step or the retry (run_records.py runs it as extract only).

This command runs one record at a time, and only demo or working records. To run
many records, with the one retry after a failed Check, use run_records.py, which
calls extract_with_retry() below.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import saved_calls  # noqa: E402  (T20: every model call is saved or replayed here)

TOOL = Path(__file__).resolve().parent
REPO = TOOL.parent.parent
SHARED = REPO / "shared"
PROMPTS = TOOL / "prompts"
OUTPUTS = REPO / "outputs"   # saved_calls.py adds extracted/<run_id>/

RECORD_NAME = re.compile(r"^([PRD]\d{3})_([ABC])\.(csv|txt)$")
MAX_TOKENS = 8000

# Lowest thinking setting each model accepted in T08 (docs/decisions.md).
# Haiku 5.5 refused "between_tools", so it runs at its default.
THINKING = {
    "claude-sonnet-5-5": {"type": "between_tools"},
    "claude-haiku-5-5": None,
}


def nullable(schema):
    return {"anyOf": [schema, {"type": "null"}]}


def is_plain(prompt_version):
    """True for a plain-lists prompt (T66, row 4): its version ends in "-plain"."""
    return prompt_version.endswith("-plain")


def label_all_current(facts):
    """Plain lists carry no status. Save every fact as "current" (plan: "a version with
    no labels is scored as all current"). Nothing else about the fact is changed."""
    return [dict(f, status="current") for f in facts]


def reply_schema(plain=False):
    """The fixed JSON shape the model must reply in: the model's part of an extracted fact.
    With plain=True the shape has no status field (plain lists, T66)."""
    lists = json.loads((SHARED / "fixed_lists.json").read_text(encoding="utf-8"))
    fact = {
        "type": "object",
        "additionalProperties": False,
        "required": ["type", "name", "name_as_written", "dose", "frequency",
                     "reaction", "status", "date", "quote"],
        "properties": {
            "type": {"type": "string", "enum": lists["record_types"]},
            "name": nullable({"type": "string"}),
            "name_as_written": nullable({"type": "string"}),
            "dose": nullable({"type": "string"}),
            "frequency": nullable({"type": "string", "enum": lists["frequencies"]}),
            "reaction": nullable({"type": "string"}),
            "status": {"type": "string", "enum": lists["statuses"]},
            "date": nullable({"type": "string"}),
            "quote": {"type": "string"},
        },
    }
    if plain:
        fact["required"].remove("status")
        del fact["properties"]["status"]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["facts"],
        "properties": {"facts": {"type": "array", "items": fact}},
    }


def short_model(model):
    return model.removeprefix("claude-")


def load_key():
    """ANTHROPIC_API_KEY from the environment, else from the git-ignored .env at the repo root."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    env = REPO / ".env"
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("ANTHROPIC_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    return key or None


def check_record_path(path):
    """Only demo and working records in T19. Returns (patient_id, hospital) or raises."""
    m = RECORD_NAME.match(path.name)
    if not m:
        raise SystemExit(f"STOP: '{path.name}' is not a hospital record name like P001_A.csv or D001_C.txt.")
    parts = {p.lower() for p in path.resolve().parts}
    if "heldout" in parts or "reserve" in parts:
        raise SystemExit("STOP: held-out and reserve records are not run here (CLAUDE.md, Held-out patients).")
    if "demo" not in parts and "working" not in parts:
        raise SystemExit("STOP: T19 runs only records in pipeline/data/demo/ or pipeline/data/working/.")
    if not path.exists():
        raise SystemExit(f"STOP: {path} does not exist.")
    return m.group(1), m.group(2)


def add_required_flags(fact):
    """The only changes made to the model's facts: flags the format rules require."""
    fact = dict(fact)
    flags = []
    if fact["type"] == "medicine" and fact["status"] == "current" and not fact["dose"]:
        flags.append("missing_dose")
    if fact["name"] is None and fact["status"] != "none_recorded":
        flags.append("unknown_name")
    fact["flags"] = flags
    return fact


def build_record(*, patient_id, hospital, source_file, run_id, model, prompt_version,
                 attempt, usage, facts, settings):
    return {
        "format_version": "1.0",
        "patient_id": patient_id,
        "hospital": hospital,
        "source_file": source_file,
        "run_id": run_id,
        "model": model,
        "prompt_version": prompt_version,
        "temperature": None,   # the model refuses temperature (T08, T56): not sent
        "settings": settings,
        "attempt": attempt,
        "usage": usage,
        "facts": [add_required_flags(f) for f in facts],
    }


def validate_record(path):
    sys.path.insert(0, str(SHARED))
    import validate as v  # shared/validate.py
    return v.check_file(path, "extracted")


def quotes_not_in_record(facts, record_text):
    """Quotes that are not word-for-word in the record. The Check step (T22) acts on these."""
    return [f["quote"] for f in facts if f["quote"] not in record_text]


def build_request(model, system, record_text, plain=False):
    """The settings sent to the API for one record. Returns (request, settings in words)."""
    request = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": [{"role": "user", "content": record_text}],
        "output_config": {"format": {"type": "json_schema", "schema": reply_schema(plain)}},
    }
    thinking = THINKING.get(model)
    if thinking:
        request["thinking"] = thinking
    settings = (f"thinking {thinking['type']}" if thinking else "thinking at model default") + \
        ", fixed JSON shape, default sampling"
    if plain:
        settings += ", plain lists (no status asked for; every fact saved as current)"
    return request, settings


def _no_call(**_):
    raise RuntimeError("a saved reply exists, so no call should be made")


# ---------------------------------------------------------------------------------
# The one retry (T22 + T19 join-up). Used by run_records.py for many records.
# ---------------------------------------------------------------------------------

RETRY_NOTE = (
    "Your reply above failed these checks against the record:\n{problems}\n\n"
    "Reply again with the full list of facts for this record, following the same rules. "
    "Copy every quote word for word from the record, and only give a dose or a name "
    "that appears in its quote."
)


def build_retry_request(first_request, first_reply_text, problems):
    """The request for the one retry: the same settings and record, plus the first reply
    and the list of problems the Check step found, so the model can fix them."""
    request = dict(first_request)
    note = RETRY_NOTE.format(problems="\n".join(f"- {p}" for p in problems))
    request["messages"] = list(first_request["messages"]) + [
        {"role": "assistant", "content": first_reply_text},
        {"role": "user", "content": note},
    ]
    return request


class ExtractFailed(Exception):
    """A record could not be read into facts (reply cut off, or not the expected JSON).
    The exact reply is saved; the message says what happened, in plain words."""


def extract_once(*, model, record_path, prompt_version, run_id, client, attempt=1,
                 problems=None, first_reply_text=None, outputs=None):
    """Get one record's facts (attempt 1, or 2 for the retry), making at most one call.

    If the saved file for this attempt already exists, it is read and NO call is made,
    so a long run that stopped halfway can simply be started again.
    Returns (record dict, reply text, made_a_call).
    """
    outputs = outputs or OUTPUTS
    patient_id, hospital = RECORD_NAME.match(record_path.name).group(1, 2)
    prompt_file = PROMPTS / f"extract_{prompt_version}.md"
    system = prompt_file.read_text(encoding="utf-8")
    record_text = record_path.read_text(encoding="utf-8")
    out_dir = outputs / "extracted" / run_id
    stem = record_path.stem + ("" if attempt == 1 else ".attempt2")
    out_json = out_dir / f"{stem}.json"

    plain = is_plain(prompt_version)
    if plain and attempt == 2:
        raise ValueError("plain lists (row 4) have no Check step, so they are never retried")
    request, settings = build_request(model, system, record_text, plain)
    if attempt == 2:
        request = build_retry_request(request, first_reply_text, problems)
        settings += ", retry after failed Check"

    if out_json.exists():   # already done in this run: replay, no call
        saved = saved_calls.load_saved(run_id, patient_id, hospital, attempt, outputs,
                                       record_path=record_path, prompt_path=prompt_file)
        return json.loads(out_json.read_text(encoding="utf-8")), saved.text, False

    saved = saved_calls.call_or_replay(run_id, patient_id, hospital, record_path, prompt_file,
                                       prompt_version, request, client.messages.create,
                                       attempt=attempt, outputs=outputs)
    if saved.details.get("stop_reason") == "max_tokens":
        raise ExtractFailed(f"{stem}: the reply was cut off at {MAX_TOKENS} tokens")
    try:
        facts = json.loads(saved.text)["facts"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise ExtractFailed(f"{stem}: the reply is not the expected JSON ({type(e).__name__})")
    if plain:
        facts = label_all_current(facts)

    usage = {k: saved.usage[k] for k in ("input_tokens", "output_tokens")}
    record = build_record(patient_id=patient_id, hospital=hospital, source_file=record_path.name,
                          run_id=run_id, model=model, prompt_version=prompt_version,
                          attempt=attempt, usage=usage, facts=facts, settings=settings)
    out_json.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record, saved.text, not saved.replayed


def extract_with_retry(*, model, record_path, prompt_version, run_id, client, outputs=None):
    """Extract one record, check it, and retry ONCE only if the Check step fails it
    (CLAUDE.md, Model calls). Uses check.check_with_retry(), so the rule for which try
    is kept lives in one place (check.py: fewer problems wins, the retry wins a tie).

    Returns a short summary: calls made, whether it retried, which attempt was kept,
    and how many problems are left. The checked files themselves are written by
    check.run() afterwards, from the saved files.
    """
    import check  # pipeline/tool/check.py

    first, first_text, called1 = extract_once(model=model, record_path=record_path,
                                              prompt_version=prompt_version, run_id=run_id,
                                              client=client, outputs=outputs)
    source_text = record_path.read_text(encoding="utf-8")
    calls = {"made": int(called1)}

    def extract_again(problems):
        second, _, called2 = extract_once(model=model, record_path=record_path,
                                          prompt_version=prompt_version, run_id=run_id,
                                          client=client, attempt=2, problems=problems,
                                          first_reply_text=first_text, outputs=outputs)
        calls["made"] += int(called2)
        return second

    result = check.check_with_retry(first, source_text, extract_again)
    return {"calls": calls["made"], "retried": result["retried"], "attempt_kept": result["attempt"],
            "problems_left": len(result["problems"]),
            "facts": len(result["checked"]["facts"]) if result["checked"] else 0}


def show(path):
    """A path relative to the repo when it is inside it, for printing."""
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def main(argv=None, client=None):
    ap = argparse.ArgumentParser(description="Extract facts from ONE hospital record (one model call).")
    ap.add_argument("--model", required=True, choices=sorted(THINKING))
    ap.add_argument("--record", required=True, type=Path)
    ap.add_argument("--prompt", default="v1")
    ap.add_argument("--run-id")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    patient_id, hospital = check_record_path(args.record)
    prompt_file = PROMPTS / f"extract_{args.prompt}.md"
    if not prompt_file.exists():
        raise SystemExit(f"STOP: no prompt file {prompt_file.relative_to(REPO)}.")
    system = prompt_file.read_text(encoding="utf-8")
    record_text = args.record.read_text(encoding="utf-8")
    run_id = args.run_id or f"{dt.date.today():%Y%m%d}-{args.prompt}-{short_model(args.model)}"
    out_dir = OUTPUTS / "extracted" / run_id
    out_json = out_dir / f"{args.record.stem}.json"
    already_saved = saved_calls.is_saved(run_id, patient_id, hospital, 1, OUTPUTS)

    print(f"Record:  {args.record.name}  (patient {patient_id}, hospital {hospital})")
    print(f"Prompt:  {prompt_file.relative_to(REPO)}  ({len(system)} characters)")
    print(f"Model:   {args.model}")
    print(f"Run ID:  {run_id}")
    print(f"Saves:   {show(out_json)} (+ .raw.txt and .call.json)")

    if out_json.exists():
        raise SystemExit("STOP: this record already has a saved extraction in this run. Saved files are never "
                         "overwritten. Use a new --run-id (e.g. add -b) if you mean to run it again.")
    if args.dry_run:
        print("Dry run: no call made." + (" A saved reply exists, so a real run would make no call either."
                                          if already_saved else ""))
        return 0

    if already_saved:
        client = client or SimpleNamespace(messages=SimpleNamespace(create=_no_call))
    elif client is None:
        key = load_key()
        if not key:
            raise SystemExit("STOP: no API key. Put ANTHROPIC_API_KEY=... in the .env file at the repo root.")
        import anthropic
        client = anthropic.Anthropic(api_key=key)

    plain = is_plain(args.prompt)
    request, settings = build_request(args.model, system, record_text, plain)
    print("Using the saved reply (no call) ..." if already_saved else "Sending 1 record (1 call) ...")
    try:
        saved = saved_calls.call_or_replay(run_id, patient_id, hospital, args.record, prompt_file,
                                           args.prompt, request, client.messages.create, attempt=1,
                                           outputs=OUTPUTS)
    except saved_calls.SavedCallError as e:
        print(f"STOPPED: {e}")
        return 1
    except Exception as e:  # turn API errors into plain words; nothing is saved
        name = type(e).__name__
        plain = {
            "AuthenticationError": "the API key was rejected. Check the key in .env.",
            "PermissionDeniedError": "the key is not allowed to use this model.",
            "NotFoundError": f"model '{args.model}' was not found.",
            "RateLimitError": "rate limit hit. Wait a minute and try once more.",
            "APIConnectionError": "could not reach the API. Check the internet connection.",
            "BadRequestError": "the API refused the request (often a setting or the JSON shape).",
        }.get(name)
        if plain is None:
            raise
        print(f"FAILED: {plain} Details: {getattr(e, 'message', e)}")
        print("Nothing was saved. Send this output to the team.")
        return 1

    text, usage = saved.text, {k: saved.usage[k] for k in ("input_tokens", "output_tokens")}
    if saved.details.get("stop_reason") == "max_tokens":
        print(f"FAILED: the reply was cut off at {MAX_TOKENS} tokens. The reply is saved; send this to the team.")
        return 1
    try:
        facts = json.loads(text)["facts"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"FAILED: the reply is not the expected JSON ({e}). The exact reply is saved in {args.record.stem}.raw.txt.")
        return 1
    if plain:
        facts = label_all_current(facts)

    record = build_record(patient_id=patient_id, hospital=hospital, source_file=args.record.name,
                          run_id=run_id, model=args.model, prompt_version=args.prompt, attempt=1,
                          usage=usage, facts=facts, settings=settings)
    out_json.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Saved.   {len(facts)} facts, {usage['input_tokens']} tokens in, {usage['output_tokens']} out.")
    problems = validate_record(out_json)
    bad_quotes = quotes_not_in_record(facts, record_text)
    if problems:
        print("Format check: problems found (the Check step will deal with these):")
        for p in problems:
            print("  -", p)
    else:
        print("Format check: OK")
    if bad_quotes:
        print(f"Quotes not found word for word in the record: {len(bad_quotes)}")
        for q in bad_quotes:
            print("  -", repr(q))
    else:
        print("Quotes: all found word for word in the record")
    return 0


if __name__ == "__main__":
    sys.exit(main())
