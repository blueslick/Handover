"""Azure baseline (T76): Microsoft Azure Text Analytics for Health, kept only for comparison.

It is not part of the tool. It sits next to the keyword baseline (T24) and the medSpaCy baseline
(T42), and reads the hospital records in the same way. It makes no Claude calls.

What it does, for each hospital record:
- Sends the record to Azure as one document (Hospital A's CSV: the header row is dropped and each
  row is one line, with commas spaced out, exactly the row text the medSpaCy baseline reads).
  Documents go in small batches. Every raw Azure reply is saved to disk before anything else is
  done with it, and a rerun reads the saved replies, so no record is ever sent twice.
- Turns Azure's items into facts with the translation rules in docs/decisions.md (T76):
  only MedicationName and Allergen items; names through the same drug list and brand table as the
  keyword and medSpaCy baselines (a name not in them gives no fact, as in medSpaCy, and is
  counted); allergy or medicine by the keyword rule; Azure's certainty, conditionality,
  association and temporal labels give the status; dose only from Azure's dosage link.
  "No known allergies" / "no regular medicines" lines come from the medSpaCy baseline's own code,
  so the two baselines treat them the same.
- Writes two records per patient, in the compiled shape:
    outputs/baseline_azure/<P>.json        Azure facts stacked (stack_merge.py), kind baseline_azure
    outputs/baseline_azure_rules/<P>.json  Azure facts through compile_patient() unchanged, as
                                           rules_row.py does, kind baseline_azure_rules
  Raw replies go to outputs/baseline_azure/replies/ and the run summary (model version, documents,
  characters, text records, calls) to outputs/baseline_azure/azure_run.json.

Azure is called through its REST API (api-version 2023-04-01) with httpx, which the project already
has. The azure-ai-textanalytics SDK is not used: it drops the "temporal" label (past / future).
The key and endpoint are read from the git-ignored .env (AZURE_LANGUAGE_KEY,
AZURE_LANGUAGE_ENDPOINT) and are never printed. medspacy is needed for the "no known allergies"
lines (optional, as in T42:  .venv/bin/pip install medspacy==1.3.1).

Usage (from the repo root, with the project venv):
    .venv/bin/python pipeline/eval/azure_baseline.py --dry-run --working --plan-heldout
    .venv/bin/python pipeline/eval/azure_baseline.py D001 P001          (test mode: one or two patients)
    .venv/bin/python pipeline/eval/azure_baseline.py --working D001
    .venv/bin/python pipeline/eval/azure_baseline.py --offline --working D001   (saved replies only)

--dry-run counts documents and characters and estimates Azure text records (1,000 characters
each, per document). It never calls Azure. It stops if the whole plan would use more than 4,000.

Held-out mode (after the freeze only): add --heldout (and --all-heldout for all 160). The script
first checks (pipeline/eval/heldout_guard.py) that the `freeze` tag exists and that every output
folder is git-ignored, and stops before opening any held-out file if not. Output then goes to
outputs/results_heldout/baseline_azure/ and baseline_azure_rules/, and the screen shows counts only.
"""

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
from pathlib import Path

EVAL = Path(__file__).resolve().parent
TOOL = EVAL.parent / "tool"  # pipeline/tool, where Daniel's compile.py lives
sys.path.insert(0, str(TOOL))

from compile import compile_patient  # noqa: E402  (Daniel's compile step, called unchanged)

import heldout_guard  # noqa: E402
from keyword_baseline import (  # noqa: E402
    WORKING, classify_name, dose_after, load_kinds, load_names, record_files, visit_date,
)
from medspacy_baseline import line_of  # noqa: E402
from stack_merge import build_record, write_record  # noqa: E402

REPO = EVAL.parents[1]
OUT = REPO / "outputs" / "baseline_azure"
OUT_RULES = REPO / "outputs" / "baseline_azure_rules"
KIND = "baseline_azure"
KIND_RULES = "baseline_azure_rules"

API_VERSION = "2023-04-01"
BATCH_SIZE = 5            # documents per Azure job ("small batches")
CHARS_PER_TEXT_RECORD = 1000
TEXT_RECORD_LIMIT = 4000  # the free tier is 5,000 a month; stop well before it
POLL_SECONDS = 2
POLL_LIMIT = 150          # about 5 minutes per job, then stop

# The medSpaCy baseline's stop words (its added ConText rules "stopped" and "discontinued").
STOP_WORDS = ("stopped", "discontinued")
COUNTED_CATEGORIES = ("MedicationName", "Allergen")


# ---------------------------------------------------------------------------
# The text sent for one record
# ---------------------------------------------------------------------------

# Build the document text for one hospital record, and the quote for each line of it.
# Hospital A: the header row is dropped, each row is one line with commas spaced out (as the
# medSpaCy baseline reads it); the quote is the row exactly as written. B and C: the text as written.
def document_text(path, hospital):
    text = path.read_text(encoding="utf-8")
    if hospital == "A":
        rows = [line for line in text.splitlines()[1:] if line.strip()]
        return "\n".join(row.replace(",", " , ") for row in rows), rows
    return text, None


# The quote for an item at a given character offset in the document.
def quote_at(doc_text, rows, offset):
    if rows is None:
        return line_of(doc_text, offset)
    return rows[doc_text.count("\n", 0, offset)]


def text_records(n_chars):
    return max(1, math.ceil(n_chars / CHARS_PER_TEXT_RECORD))


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Saved replies: read them all, so nothing already answered is sent again
# ---------------------------------------------------------------------------

# Every saved reply file holds {"request": {...}, "reply": <raw Azure JSON>}. Return
# {document id: (document result, model version, text hash sent)}.
def load_saved(replies_dir):
    saved = {}
    for path in sorted(Path(replies_dir).glob("batch_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        sent = {d["id"]: text_hash(d["text"]) for d in data["request"]["analysisInput"]["documents"]}
        for doc, version in documents_in_reply(data["reply"]):
            saved[doc["id"]] = (doc, version, sent.get(doc["id"]))
    return saved


# The per-document results inside one raw job reply, each with the model version Azure reported.
def documents_in_reply(reply):
    out = []
    for task in reply.get("tasks", {}).get("items", []):
        results = task.get("results") or {}
        version = results.get("modelVersion")
        for doc in results.get("documents", []):
            out.append((doc, version))
        for err in results.get("errors", []):
            raise SystemExit(f"STOP: Azure returned an error for document {err.get('id')}: "
                             f"{err.get('error', {}).get('code')}")
    return out


# ---------------------------------------------------------------------------
# Calling Azure (only for documents with no saved reply)
# ---------------------------------------------------------------------------

# Read the Azure key and endpoint from the environment, else from the git-ignored .env.
# Neither is ever printed.
def azure_settings():
    found = {k: os.environ.get(k) for k in ("AZURE_LANGUAGE_KEY", "AZURE_LANGUAGE_ENDPOINT")}
    env = REPO / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            name = name.strip()
            if name in found and not found[name]:
                found[name] = value.strip().strip('"').strip("'")
    missing = [k for k, v in found.items() if not v]
    if missing:
        raise SystemExit(f"STOP: {' and '.join(missing)} missing from .env. Nothing was sent.")
    return found["AZURE_LANGUAGE_KEY"], found["AZURE_LANGUAGE_ENDPOINT"].rstrip("/")


# Send one batch as one Azure job, wait for it, and return (request body, raw final reply, HTTP calls).
def call_azure(documents, key, endpoint):
    import httpx
    body = {
        "displayName": "handover-t76",
        "analysisInput": {"documents": [{"id": d["id"], "language": "en", "text": d["text"]}
                                        for d in documents]},
        "tasks": [{"kind": "Healthcare", "taskName": "health",
                   "parameters": {"modelVersion": "latest", "stringIndexType": "UnicodeCodePoint"}}],
    }
    headers = {"Ocp-Apim-Subscription-Key": key, "Content-Type": "application/json"}
    calls = 0
    with httpx.Client(timeout=60) as client:
        # Submit the job. A 429 (too many requests) was not accepted, so waiting and sending again is safe.
        for _ in range(5):
            calls += 1
            post = client.post(f"{endpoint}/language/analyze-text/jobs",
                               params={"api-version": API_VERSION}, json=body, headers=headers)
            if post.status_code != 429:
                break
            time.sleep(float(post.headers.get("Retry-After", 10)))
        if post.status_code != 202:
            raise SystemExit(f"STOP: Azure refused the job (HTTP {post.status_code}). Nothing was saved.")
        location = post.headers["operation-location"]
        # Wait for the job to finish.
        for _ in range(POLL_LIMIT):
            time.sleep(POLL_SECONDS)
            calls += 1
            got = client.get(location, headers=headers)
            if got.status_code == 429:
                continue
            got.raise_for_status()
            reply = got.json()
            if reply.get("status") in ("succeeded", "failed", "partiallyCompleted", "cancelled"):
                return body, reply, calls
    raise SystemExit("STOP: an Azure job did not finish in time. Nothing was saved for it.")


# Send every document that has no saved reply, in batches. Each raw reply is written to disk
# straight away. Returns the number of HTTP calls made.
def fetch_missing(documents, saved, replies_dir, key, endpoint):
    todo = [d for d in documents if d["id"] not in saved]
    calls = 0
    replies_dir = Path(replies_dir)
    replies_dir.mkdir(parents=True, exist_ok=True)
    start = len(list(replies_dir.glob("batch_*.json")))
    for n, i in enumerate(range(0, len(todo), BATCH_SIZE)):
        batch = todo[i:i + BATCH_SIZE]
        body, reply, used = call_azure(batch, key, endpoint)
        calls += used
        path = replies_dir / f"batch_{start + n + 1:04d}.json"
        path.write_text(json.dumps({"request": body, "reply": reply}, indent=1, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        if reply.get("status") != "succeeded":
            raise SystemExit(f"STOP: an Azure job ended with status {reply.get('status')}. "
                             f"Its reply is saved as {path.name}.")
        for doc, version in documents_in_reply(reply):
            saved[doc["id"]] = (doc, version, text_hash(next(d["text"] for d in batch if d["id"] == doc["id"])))
    return calls


# ---------------------------------------------------------------------------
# Translation rules (docs/decisions.md, T76)
# ---------------------------------------------------------------------------

# The entity index a relation reference points at, e.g. "#/results/documents/0/entities/3" -> 3.
def ref_index(ref):
    return int(ref.rsplit("/", 1)[-1])


# For each medication entity: the text of its dosage link, and whether a linked Course says stopped.
def links_by_entity(doc):
    entities = doc.get("entities", [])
    dosage, course_stop = {}, set()
    for rel in doc.get("relations", []):
        roles = {}
        for member in rel.get("entities", []):
            roles.setdefault(member["role"], []).append(ref_index(member["ref"]))
        meds = roles.get("Medication", [])
        if rel.get("relationType") == "DosageOfMedication":
            for d in roles.get("Dosage", []):
                for m in meds:
                    dosage.setdefault(m, entities[d]["text"])
        elif rel.get("relationType") == "CourseOfMedication":
            for c in roles.get("Course", []):
                words = re.findall(r"[a-z]+", entities[c]["text"].lower())
                if any(w in STOP_WORDS for w in words):
                    course_stop.update(meds)
    return dosage, course_stop


# Our generic name for an item's text, or None when it is not in the drug list or brand table.
def our_name(written, names):
    low = written.strip().lower()
    return names.get(low) or names.get(low.replace(" and ", " / "))


# Turn one Azure document result into facts in the extracted shape. Also returns the number of
# MedicationName / Allergen items that had no name in our lists (they give no fact).
def translate(doc, doc_text, rows, date, names, kinds):
    dosage, course_stop = links_by_entity(doc)
    facts, unnamed = [], 0
    for i, ent in enumerate(doc.get("entities", [])):
        category = ent.get("category")
        if category not in COUNTED_CATEGORIES:
            continue
        written = ent["text"]
        generic = our_name(written, names)
        if generic is None:
            unnamed += 1
            continue
        a = ent.get("assertion") or {}
        # Rules 4, 5 and 8: about someone else, negated, or conditional -> no fact.
        if a.get("association") == "other":
            continue
        if a.get("certainty") in ("negative", "negativePossible"):
            continue
        if a.get("conditionality") == "conditional":
            continue
        quote = quote_at(doc_text, rows, ent["offset"])
        # Rule 3: allergy or medicine.
        fact_type = "allergy" if category == "Allergen" else classify_name(generic, quote, kinds)
        dose = None
        if fact_type == "allergy":
            # Rule 6: a possible allergy is suspected.
            possible = a.get("certainty") in ("positivePossible", "neutralPossible")
            status = "suspected" if possible else "current"
        else:
            # Rules 7, 8, 9: stopped, planned, otherwise current.
            if a.get("temporality") == "past" or i in course_stop:
                status = "stopped"
            elif a.get("temporality") == "future" or a.get("conditionality") == "hypothetical":
                status = "planned"
            else:
                status = "current"
            # Rule 10: dose only from Azure's own dosage link, read with the baselines' dose helper.
            if i in dosage:
                dose = dose_after(dosage[i], 0)
        flags = ["missing_dose"] if fact_type == "medicine" and status == "current" and dose is None else []
        facts.append({
            "type": fact_type, "name": generic, "name_as_written": written,
            "dose": dose, "frequency": None, "reaction": None, "status": status,
            "date": date, "quote": quote, "flags": flags,
        })
    return facts, unnamed


# The medSpaCy baseline's "no known allergies" / "no regular medicines" facts for one record
# (rule 5's exception): its own code, so the two baselines treat those lines the same.
def make_none_facts():
    import medspacy_baseline as mb
    names, kinds = load_names(), load_kinds()
    nlp = mb.build_nlp(names)

    def none_facts(path, hospital):
        return [f for f in mb.extract_record(path, hospital, names, kinds, nlp)
                if f["status"] == "none_recorded"]
    return none_facts


# ---------------------------------------------------------------------------
# One patient, and the whole run
# ---------------------------------------------------------------------------

def documents_for(patient_id):
    files = record_files(patient_id)
    if len(files) != 3:
        raise SystemExit(f"{patient_id}: expected 3 hospital records, found {len(files)}")
    docs = []
    for path in files:
        hospital = path.stem.split("_")[-1]
        text, rows = document_text(path, hospital)
        docs.append({"id": path.stem, "path": path, "hospital": hospital, "text": text, "rows": rows})
    return docs


# Build one patient's two records from saved Azure replies. Returns (stacked, compiled, unnamed count).
def build_patient(patient_id, docs, saved, names, kinds, none_facts):
    extractions, unnamed = [], 0
    for d in docs:
        result, _version, sent_hash = saved[d["id"]]
        if sent_hash != text_hash(d["text"]):
            raise SystemExit(f"STOP: the saved reply for {d['id']} was for different text. "
                             "The record changed after it was sent.")
        raw = d["path"].read_text(encoding="utf-8")
        date = visit_date(d["path"], d["hospital"], raw)
        facts, n = translate(result, d["text"], d["rows"], date, names, kinds)
        unnamed += n
        facts += none_facts(d["path"], d["hospital"])
        extractions.append({"patient_id": patient_id, "hospital": d["hospital"],
                            "source_file": d["path"].name, "facts": facts})
    stacked = build_record(KIND, patient_id, None, extractions)
    compiled = compile_patient(patient_id, extractions)
    compiled["kind"] = KIND_RULES
    return stacked, compiled, unnamed


# Count documents, characters and text records for a list of patients (no Azure call).
def plan(ids):
    docs = [d for pid in ids for d in documents_for(pid)]
    chars = sum(len(d["text"]) for d in docs)
    records = sum(text_records(len(d["text"])) for d in docs)
    return len(docs), chars, records


def main():
    ap = argparse.ArgumentParser(description="Azure baseline (T76). See the top of this file.")
    ap.add_argument("patients", nargs="*", help="e.g. D001 P001")
    ap.add_argument("--working", action="store_true", help="run P001 to P020")
    ap.add_argument("--dry-run", action="store_true", help="count documents and text records; no Azure call")
    ap.add_argument("--plan-heldout", action="store_true",
                    help="with --dry-run: also count the 160 held-out patients (counts only; needs the freeze tag)")
    ap.add_argument("--offline", action="store_true", help="use saved replies only; stop if one is missing")
    ap.add_argument("--out-dir", default=None, help="stacked records (default outputs/baseline_azure)")
    ap.add_argument("--rules-out-dir", default=None, help="compiled records (default outputs/baseline_azure_rules)")
    heldout_guard.add_heldout_args(ap)
    args = ap.parse_args()

    ids = list(args.patients) + (WORKING if args.working else [])
    if not ids and not args.all_heldout:
        ap.error("give patient IDs, or --working, or --all-heldout")
    ids = list(dict.fromkeys(heldout_guard.pick_ids(ap, args, ids)))
    out_dir = heldout_guard.pick_out_dir(args.out_dir, ids, OUT, "baseline_azure")
    rules_dir = heldout_guard.pick_out_dir(args.rules_out_dir, ids, OUT_RULES, "baseline_azure_rules")
    replies_dir = out_dir / "replies"

    # Dry run: counts only. With --plan-heldout the held-out total is added (freeze tag needed).
    if args.dry_run:
        n_docs, chars, records = plan(ids)
        print(f"This run: {len(ids)} patients, {n_docs} documents, {chars:,} characters, "
              f"{records:,} text records, {math.ceil(n_docs / BATCH_SIZE)} Azure jobs")
        total = records
        if args.plan_heldout:
            heldout_guard.require_freeze_tag()
            held = [p for p in heldout_guard.heldout_ids() if p not in ids]
            h_docs, h_chars, h_records = plan(held)
            print(f"Held-out: {len(held)} patients, {h_docs} documents, {h_chars:,} characters, "
                  f"{h_records:,} text records, {math.ceil(h_docs / BATCH_SIZE)} Azure jobs")
            total += h_records
        print(f"Whole plan: {total:,} text records (limit {TEXT_RECORD_LIMIT:,})")
        if total > TEXT_RECORD_LIMIT:
            raise SystemExit("STOP: the plan is over the text-record limit. Nothing was sent.")
        return

    # Held-out guard: the freeze tag and git-ignored folders, checked before any record is opened.
    outputs = ([out_dir / f"{p}.json" for p in ids] + [rules_dir / f"{p}.json" for p in ids]
               + [replies_dir / "batch_0001.json", out_dir / "azure_run.json"])
    hidden = heldout_guard.guard_run(ids, outputs)
    if hidden:
        heldout_guard.require_three_records(ids, record_files)

    docs_by_patient = {pid: documents_for(pid) for pid in ids}
    all_docs = [d for pid in ids for d in docs_by_patient[pid]]
    saved = load_saved(replies_dir)
    missing = [d for d in all_docs if d["id"] not in saved]
    calls = 0
    if missing:
        if args.offline:
            raise SystemExit(f"STOP: {len(missing)} documents have no saved reply (--offline).")
        n_records = sum(text_records(len(d["text"])) for d in missing)
        print(f"Sending {len(missing)} documents ({n_records} text records) to Azure "
              f"in {math.ceil(len(missing) / BATCH_SIZE)} jobs.")
        key, endpoint = azure_settings()
        calls = fetch_missing(all_docs, saved, replies_dir, key, endpoint)

    names, kinds = load_names(), load_kinds()
    none_facts = make_none_facts()
    total_facts = unnamed = 0
    for pid in ids:
        stacked, compiled, n = build_patient(pid, docs_by_patient[pid], saved, names, kinds, none_facts)
        write_record(stacked, out_dir / f"{pid}.json")
        write_record(compiled, rules_dir / f"{pid}.json")
        heldout_guard.say(pid, len(stacked["facts"]), out_dir / f"{pid}.json", hidden)
        total_facts += len(stacked["facts"])
        unnamed += n

    # The run summary: model version(s), documents, characters, text records, calls. Counts only.
    versions = sorted({saved[d["id"]][1] for d in all_docs if saved[d["id"]][1]})
    summary = {
        "task": "T76", "api_version": API_VERSION, "model_versions": versions,
        "patients": len(ids), "documents": len(all_docs),
        "characters": sum(len(d["text"]) for d in all_docs),
        "text_records": sum(text_records(len(d["text"])) for d in all_docs),
        "documents_sent_this_run": len(missing), "http_calls_this_run": calls,
        "facts_stacked": total_facts, "items_with_no_name_in_our_lists": unnamed,
    }
    run_file = out_dir / "azure_run.json"
    if run_file.exists():
        before = json.loads(run_file.read_text(encoding="utf-8"))
        summary["http_calls_all_runs"] = before.get("http_calls_all_runs", 0) + calls
    else:
        summary["http_calls_all_runs"] = calls
    run_file.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"{len(ids)} patients, {len(all_docs)} documents, {total_facts} stacked facts, "
          f"{unnamed} Azure items with no name in our lists, model version {', '.join(versions)}, "
          f"{calls} HTTP calls this run")


if __name__ == "__main__":
    main()
