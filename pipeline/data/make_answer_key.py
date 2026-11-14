"""Build answer keys (T14): the correct compiled record for each patient.

The answer key is built from what the record maker (T12 templates, T13 placement)
actually wrote into each hospital record, not from a model. It applies the six
compile rules from docs/Handover_Pipeline_and_Frontend_Plan.md with its own code,
separate from pipeline/tool/compile.py, so the tool is never scored against itself.

Input: "written facts", one entry per hospital record for a patient:

    [
      {"hospital": "A", "file": "P014_A.csv",
       "facts": [<facts in the extracted-fact shape, see shared/schema/extracted.schema.json>]},
      {"hospital": "B", "file": "P014_B.txt", "facts": [...]},
      ...
    ]

Each fact is the perfect extraction of that record: generic lowercase `name`
(null only for none_recorded), `name_as_written`, `dose`, `frequency`, `reaction`,
`status`, `date` (never null: the date the record gives, else its visit date),
`quote` (verbatim from the record) and `flags` (normally []).

Output: P014_key.json next to the records, compiled shape, kind "answer_key".

Usage:
    python pipeline/data/make_answer_key.py --written path/to/P014_written.json [...]
    python pipeline/data/make_answer_key.py --all     (once wired to the T12 templates)

Held-out and reserve patients: the script reads and writes their files but only
prints patient IDs and counts, never fact contents (CLAUDE.md, Held-out patients).
"""
import argparse
import json
import re
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent
REPO = DATA.parent.parent
SPLIT_DIRS = {"D": "demo", "R": "reserve"}
TYPE_ORDER = {"allergy": 0, "medicine": 1, "diagnosis": 2, "operation": 3}
CRITICAL = {"allergy", "medicine"}


class KeyError_(Exception):
    """A problem in the written facts. Message is safe to print for held-out patients."""


# ---------------------------------------------------------------- helpers

def is_hidden(patient_id):
    """True for held-out and reserve patients, whose contents must never be printed."""
    if patient_id.startswith("R"):
        return True
    if patient_id.startswith("P"):
        return int(patient_id[1:]) > 20
    return False


def patient_dir(patient_id):
    if patient_id[0] in SPLIT_DIRS:
        return DATA / SPLIT_DIRS[patient_id[0]] / patient_id
    return DATA / ("heldout" if is_hidden(patient_id) else "working") / patient_id


def norm(text):
    return re.sub(r"\s+", " ", text.strip().lower()) if text else None


def compatible(a, b):
    """Two entries say the same thing. A blank dose, frequency or reaction means
    'not stated', so it fits any value (a stop note rarely repeats the dose)."""
    if a["status"] != b["status"]:
        return False
    for field in ("dose", "frequency"):
        if a[field] and b[field] and a[field] != b[field]:
            return False
    if a["reaction"] and b["reaction"] and norm(a["reaction"]) != norm(b["reaction"]):
        return False
    return True


def same_as_run(e, run):
    """e says the same as a run, judged on the run's stated values, not its last line."""
    rep = {"status": run[0]["status"], "dose": filled(run, "dose"),
           "frequency": filled(run, "frequency"), "reaction": filled(run, "reaction")}
    return compatible(e, rep)


def filled(entries, field):
    """Latest stated value of a field across a run of compatible entries."""
    for e in reversed(entries):
        if e[field]:
            return e[field]
    return None


def order(e):
    return (e["date"], e["hospital"])


# ---------------------------------------------------------------- one drug / allergy / diagnosis

def runs(entries):
    """Split a name's entries, oldest first, into runs of compatible values.
    Several entries on the latest date that disagree come back as `tied`."""
    entries = sorted(entries, key=order)
    latest_date = entries[-1]["date"]
    last_day = [e for e in entries if e["date"] == latest_date]
    tied = []
    for e in last_day:
        match = next((t for t in tied if same_as_run(e, t)), None)
        if match:
            match.append(e)
        else:
            tied.append([e])
    earlier = [e for e in entries if e["date"] != latest_date]
    seq = []
    for e in earlier:
        if seq and same_as_run(e, seq[-1]):
            seq[-1].append(e)
        else:
            seq.append([e])
    return seq, tied


def history_entry(run):
    last = run[-1]
    return {"status": last["status"], "dose": filled(run, "dose"),
            "frequency": filled(run, "frequency"), "hospital": last["hospital"],
            "date": last["date"], "quote": last["quote"]}


def make_fact(patient_id, ftype, current, history, all_entries):
    """current: entries stating the current value (rule 1: all become sources)."""
    latest = max(current, key=order)
    dose = filled(current, "dose") if ftype == "medicine" else None
    freq = filled(current, "frequency") if ftype == "medicine" else None
    if ftype == "medicine" and current[0]["status"] == "stopped" and not dose:
        # A stop note rarely repeats the dose: show the last dose it was taken at.
        for h in reversed(history):
            if h["dose"]:
                dose, freq = h["dose"], freq or h["frequency"]
                break
    flags = []
    if ftype == "medicine" and current[0]["status"] == "current":
        if not dose:
            flags.append("missing_dose")
        if any(h["status"] == "current" and h["dose"] and h["dose"] != dose for h in history):
            flags.append("dose_changed")  # rule 3
    return {
        "fact_id": None, "patient_id": patient_id, "type": ftype,
        "name": latest["name"], "name_as_written": latest["name_as_written"],
        "dose": dose, "frequency": freq,
        "reaction": filled(current, "reaction") if ftype == "allergy" else None,
        "status": latest["status"], "hospital": latest["hospital"],
        "date": latest["date"], "quote": latest["quote"],
        "sources": [{"hospital": e["hospital"], "date": e["date"], "quote": e["quote"],
                     "file": e["file"]} for e in sorted(current, key=order)],
        "history": history, "flags": flags, "conflict_group": None,
    }


def compile_name(patient_id, ftype, entries):
    """Rules 1 to 4 and 6 for one name. Returns (facts, is_conflict)."""
    seq, tied = runs(entries)
    if len(tied) == 1:
        # Rules 2 and 3: the latest dated value wins, earlier different values
        # become history. Rule 4: silence never shows up here, because a record
        # that doesn't mention the name gives no entry at all.
        current = tied[0]
        if seq and all(same_as_run(c, seq[-1]) for c in current):
            current = seq.pop() + current
        history = [history_entry(r) for r in seq]
        return [make_fact(patient_id, ftype, current, history, entries)], False
    # Rule 6: hospitals disagree on the same latest date and nothing settles it.
    # Every side is kept; earlier history goes on each side.
    history = [history_entry(r) for r in seq]
    return [make_fact(patient_id, ftype, side, list(history), entries) for side in tied], True


# ---------------------------------------------------------------- one patient

def build_key(patient_id, records):
    """records: the written-facts list described at the top. Returns the key dict."""
    if not records:
        raise KeyError_(f"{patient_id}: no records given")
    by_name, none_rec, built_from = {}, {}, []
    for rec in records:
        hosp, fname = rec["hospital"], rec["file"]
        if not re.fullmatch(rf"{patient_id}_{hosp}\.(csv|txt)", fname):
            raise KeyError_(f"{patient_id}: file name {fname} doesn't match hospital {hosp}")
        built_from.append(fname)
        for i, f in enumerate(rec["facts"]):
            where = f"{patient_id} {fname} fact {i}"
            if not f.get("date") or not f.get("quote"):
                raise KeyError_(f"{where}: every written fact needs a date and a quote")
            e = dict(f, hospital=hosp, file=fname)
            if f["status"] == "none_recorded":
                if f["name"] is not None:
                    raise KeyError_(f"{where}: none_recorded must have name null")
                none_rec.setdefault(f["type"], []).append(e)
            else:
                if not f["name"] or f["name"] != f["name"].lower():
                    raise KeyError_(f"{where}: answer key needs the lowercase generic name")
                by_name.setdefault((f["type"], f["name"]), []).append(e)

    facts, groups = [], []          # groups: lists of facts that conflict together
    for (ftype, name), entries in by_name.items():
        made, conflict = compile_name(patient_id, ftype, entries)
        facts.extend(made)
        if conflict:
            groups.append(made)

    for ftype, entries in none_rec.items():
        # Several hospitals saying "none" is one fact with several sources (rule 1).
        fact = make_fact(patient_id, ftype, entries, [], entries)
        facts.append(fact)
        if ftype == "allergy":
            # Rule 5: any recorded allergy, at any date, conflicts with "no known
            # allergies". Allergies are never removed automatically.
            sides = [f for f in facts if f["type"] == "allergy" and f is not fact]
        elif ftype == "medicine":
            # Rule 6: "no regular medicines" contradicts a medicine still current
            # that was recorded on or before that date. A medicine first recorded
            # after it is a new start, not a disagreement.
            sides = [f for f in facts if f["type"] == "medicine" and f["status"] == "current"
                     and min(s["date"] for s in f["sources"]) <= fact["date"]]
        else:
            sides = []
        if sides:
            groups.append([fact] + sides)

    # Merge groups that share a fact, so one fact never sits in two groups.
    merged = []
    for g in groups:
        ids = {id(f) for f in g}
        hits = [m for m in merged if ids & {id(f) for f in m}]
        for h in hits:
            merged.remove(h)
            g = h + [f for f in g if id(f) not in {id(x) for x in h}]
        merged.append(g)

    facts.sort(key=lambda f: (TYPE_ORDER[f["type"]], f["name"] is None, f["name"] or "",
                              f["status"], f["date"], f["hospital"]))
    for n, f in enumerate(facts, 1):
        f["fact_id"] = f"{patient_id}-F{n:02d}"
    merged.sort(key=lambda g: min(facts.index(f) for f in g))
    for n, g in enumerate(merged, 1):
        for f in g:
            f["conflict_group"] = f"{patient_id}-C{n}"
            if "conflict" not in f["flags"]:
                f["flags"].append("conflict")

    return {"format_version": "1.0", "kind": "answer_key", "patient_id": patient_id,
            "run_id": None, "built_from": sorted(built_from), "facts": facts}


def check_quotes(patient_id, records, folder):
    """Every quote must be a verbatim substring of its record file, if the file exists."""
    problems = []
    for rec in records:
        path = folder / rec["file"]
        if not path.exists():
            problems.append(f"{patient_id}: record file {rec['file']} not found, quotes not checked")
            continue
        text = path.read_text(encoding="utf-8")
        for i, f in enumerate(rec["facts"]):
            if f["quote"] not in text:
                problems.append(f"{patient_id} {rec['file']} fact {i}: quote not found in the record")
    return problems


# ---------------------------------------------------------------- command line

def written_facts_from_templates(patient_id):
    """Hook for T12/T13: return the written-facts list for one patient straight from
    the record maker, so no extra file is needed in the patient folder."""
    raise NotImplementedError(
        "Not wired to the T12 templates yet. Use --written for now. "
        "Once make_records.py is pushed, return its per-record facts here.")


def write_key(patient_id, records, out_dir=None, strict_quotes=True):
    folder = out_dir or patient_dir(patient_id)
    problems = check_quotes(patient_id, records, patient_dir(patient_id))
    if problems and strict_quotes:
        raise KeyError_("; ".join(problems))
    key = build_key(patient_id, records)
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"{patient_id}_key.json"
    out.write_text(json.dumps(key, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    sys.path.insert(0, str(REPO / "shared"))
    from validate import check_file
    bad = check_file(out, "compiled")
    if bad:
        raise KeyError_(f"{patient_id}: key failed shared/validate.py ({len(bad)} problems)"
                        + ("" if is_hidden(patient_id) else ": " + "; ".join(bad)))
    n_conf = len({f["conflict_group"] for f in key["facts"] if f["conflict_group"]})
    return out, len(key["facts"]), n_conf, problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--written", nargs="*", default=[], help="written-facts JSON files, one per patient, named <ID>_written.json or holding {'patient_id', 'records'}")
    ap.add_argument("--all", action="store_true", help="every patient, from the T12 templates")
    ap.add_argument("--out", type=Path, help="write keys here instead of the patient folders (for tests)")
    ap.add_argument("--no-quote-check", action="store_true", help="skip the record-file quote check")
    args = ap.parse_args()

    jobs = []
    for p in args.written:
        doc = json.loads(Path(p).read_text(encoding="utf-8"))
        if isinstance(doc, dict):
            jobs.append((doc["patient_id"], doc["records"]))
        else:
            jobs.append((Path(p).name.split("_")[0], doc))
    if args.all:
        ids = [l.strip() for f in ("working_ids.txt", "heldout_ids.txt")
               for l in (DATA / "split" / f).read_text().splitlines() if l.strip()]
        jobs += [(pid, written_facts_from_templates(pid)) for pid in ids]
    if not jobs:
        ap.error("give --written files or --all")

    failed = 0
    for pid, records in jobs:
        try:
            out, n, c, warn = write_key(pid, records, args.out, not args.no_quote_check)
            note = f", {len(warn)} warnings" if warn else ""
            print(f"OK   {pid}: {n} facts, {c} conflict groups{note}")
            if warn and not is_hidden(pid):
                for w in warn:
                    print(f"     {w}")
        except KeyError_ as e:
            failed += 1
            print(f"FAIL {pid}: {e if not is_hidden(pid) else 'problem in written facts (contents hidden: held-out)'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
