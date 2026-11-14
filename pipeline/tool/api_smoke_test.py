"""T08: send ONE test record to the Claude API and report what came back.

This is a plumbing check, not the real extraction (that is T19). It answers:
  1. Is the API key in .env found and accepted?
  2. Does the model ID exist?
  3. Does the model accept the settings we plan to use: thinking switched to
     its lowest level ("between_tools") and a fixed JSON shape (output_config)?
     Note: Claude 5.5 models refuse `temperature` (any value) and refuse
     thinking "disabled", so CLAUDE.md's "temperature 0, no extended thinking"
     cannot be followed word for word. See docs/decisions.md (T08).
  4. Does the reply come back as JSON?
  5. How many tokens did one record use? (to recheck the spend limit)

It makes exactly one call. It uses the demo patient (D001), which is never
scored, so no working or held-out patient is sent.

Run from the repo root:
    .venv/bin/python pipeline/tool/api_smoke_test.py
    .venv/bin/python pipeline/tool/api_smoke_test.py --model claude-sonnet-5-5

The reply and its token usage are saved to outputs/smoke/<run_id>.json.
The API key is never printed or saved.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_RECORD = REPO / "pipeline" / "data" / "demo" / "D001" / "D001_C.txt"
DEFAULT_MODEL = "claude-haiku-5-5"
OUT_DIR = REPO / "outputs" / "smoke"

SCHEMA = {
    "type": "object",
    "properties": {
        "allergies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "quote": {"type": "string"}},
                "required": ["name", "quote"],
                "additionalProperties": False,
            },
        },
        "medicines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "dose": {"type": "string"},
                    "frequency": {"type": "string"},
                    "quote": {"type": "string"},
                },
                "required": ["name", "dose", "frequency", "quote"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["allergies", "medicines"],
    "additionalProperties": False,
}

INSTRUCTION = (
    "You are reading one hospital record. List the patient's allergies and "
    "medicines exactly as the record states them. Reply with JSON only, no "
    "other text, in this shape: "
    '{"allergies": [{"name": "...", "quote": "..."}], '
    '"medicines": [{"name": "...", "dose": "...", "frequency": "...", "quote": "..."}]}. '
    "Use an empty list if there are none. Copy each quote word for word from the record."
)


def load_api_key() -> str | None:
    """Read ANTHROPIC_API_KEY from the environment or from the repo's .env file."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key.strip()
    env_path = REPO / ".env"
    if not env_path.exists():
        return None
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("export "):
                line = line[len("export "):]
            if line.startswith("ANTHROPIC_API_KEY="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                return value or None
    return None


def short_model_name(model: str) -> str:
    return model.removeprefix("claude-")


def parse_json_reply(text: str):
    """Return (parsed_or_None, note). Accepts a reply wrapped in ``` fences."""
    cleaned = text.strip()
    note = "plain JSON"
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
        note = "JSON inside ``` fences (T19's prompt should stop this)"
    try:
        return json.loads(cleaned), note
    except json.JSONDecodeError:
        return None, "NOT valid JSON"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"exact model ID (default {DEFAULT_MODEL})")
    ap.add_argument("--record", type=Path, default=DEFAULT_RECORD, help="record file to send (default: demo D001_C.txt)")
    args = ap.parse_args(argv)

    record_path = args.record if args.record.is_absolute() else (Path.cwd() / args.record)
    if {"heldout", "reserve"} & set(record_path.resolve().parts):
        print("STOP: this test must not send a held-out record. Use the demo or a working record.")
        return 2
    if not record_path.exists():
        print(f"STOP: record not found: {record_path}")
        return 2

    key = load_api_key()
    if not key:
        print("STOP: no API key found.")
        print("  Make a file called .env in the top folder of the repo with one line:")
        print("  ANTHROPIC_API_KEY=<your key>")
        print("  (Type it in yourself. Never paste the key into a chat.)")
        return 2

    try:
        import anthropic
    except ImportError:
        print("STOP: the 'anthropic' package is not installed in this .venv.")
        print("  Run: .venv/bin/pip install -r pipeline/requirements.txt")
        return 2

    with open(record_path, encoding="utf-8") as f:
        record_text = f.read()

    client = anthropic.Anthropic(api_key=key)

    # Try the full planned settings first. If the model refuses one, drop it,
    # note which one, and try again (at most 3 calls in total).
    attempts = [
        ("lowest thinking + fixed JSON shape",
         {"thinking": {"type": "between_tools"},
          "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}}}),
        ("fixed JSON shape only (thinking left at the model's default)",
         {"output_config": {"format": {"type": "json_schema", "schema": SCHEMA}}}),
        ("plain request (no extra settings)", {}),
    ]
    refused: list[str] = []
    resp = None
    settings_used = None
    print(f"Sending 1 record ({record_path.name}) to {args.model} ...")
    for label, extra in attempts:
        try:
            resp = client.messages.create(
                model=args.model,
                max_tokens=2000,
                system=INSTRUCTION,
                messages=[{"role": "user", "content": record_text}],
                **extra,
            )
            settings_used = label
            break
        except anthropic.AuthenticationError:
            print("FAILED: the API key was rejected. Check the key in .env (no spaces, no quotes needed).")
            return 1
        except anthropic.PermissionDeniedError as e:
            print(f"FAILED: the key is not allowed to use this model or workspace. Details: {e.message}")
            return 1
        except anthropic.NotFoundError:
            print(f"FAILED: model '{args.model}' was not found. Check the exact model ID.")
            return 1
        except anthropic.RateLimitError:
            print("FAILED: rate limit hit. Wait a minute and try once more.")
            return 1
        except anthropic.BadRequestError as e:
            msg = str(e.message)
            if "credit" in msg.lower() or "billing" in msg.lower():
                print("FAILED: the account is out of credit or the spend limit is reached. Check Billing in the Claude Console.")
                return 1
            print(f"  The model refused '{label}': {msg}")
            refused.append(f"{label}: {msg}")
        except anthropic.APIConnectionError:
            print("FAILED: could not reach the API. Check the internet connection.")
            return 1
    if resp is None:
        print("FAILED: the model refused every set of settings. Send this output to the team.")
        return 1

    text = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
    parsed, json_note = parse_json_reply(text)
    usage = {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
    }

    today = dt.date.today().strftime("%Y%m%d")
    run_id = f"{today}-smoke-{short_model_name(args.model)}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{run_id}.json"
    saved = {
        "task": "T08",
        "run_id": run_id,
        "model_requested": args.model,
        "model_returned": resp.model,
        "settings_used": settings_used,
        "settings_refused": refused,
        "thinking_blocks_returned": sum(1 for b in resp.content if getattr(b, "type", "") == "thinking"),
        "record": record_path.relative_to(REPO).as_posix() if record_path.is_relative_to(REPO) else record_path.name,
        "stop_reason": resp.stop_reason,
        "usage": usage,
        "reply_is_json": parsed is not None,
        "reply_text": text,
        "reply_parsed": parsed,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(saved, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print()
    print("SUCCESS: the API answered.")
    print(f"  Model that answered : {resp.model}")
    print(f"  Settings that worked: {settings_used}")
    if refused:
        print(f"  Settings refused    : {len(refused)} (details in the saved file)")
    print(f"  Reply format        : {json_note}")
    print(f"  Finished because    : {resp.stop_reason}")
    print(f"  Tokens used         : {usage['input_tokens']} in, {usage['output_tokens']} out")
    if parsed is not None:
        print(f"  Found               : {len(parsed.get('allergies', []))} allergies, "
              f"{len(parsed.get('medicines', []))} medicines")
    shown = out_path.relative_to(REPO).as_posix() if out_path.is_relative_to(REPO) else out_path
    print(f"  Saved to            : {shown}")
    print()
    print("Spend check: a full run is about 300 calls (100 patients x 3 records).")
    print(f"  At this size that is roughly {usage['input_tokens'] * 300:,} input and "
          f"{usage['output_tokens'] * 300:,} output tokens per run. The real prompt (T19) will be longer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
