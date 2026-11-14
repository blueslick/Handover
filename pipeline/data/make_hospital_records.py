"""Generate the three hospital records for each patient (T13). Code writes the records, not an AI.

For one patient this script decides three things, then hands each hospital's "visit" to the
T12 templates (pipeline/data/templates/make_records.py), which turn it into text:

1. Each hospital's visit date. The order of the three hospitals is shuffled per patient, so the
   newest record is not always the same hospital.
       latest visit   2 to 21 days before 18 Nov 2021, and never before the newest current medicine
       middle visit   30 to 120 days before the latest one
       earliest visit 90 to 365 days before the middle one
   (A planted stop moves the earliest visit to just before that stop; see trap 1.)

2. Which facts each hospital mentions. A hospital writes what was true on its visit date:
   - allergies and diagnoses that started on or before the visit
   - current medicines that started on or before the visit (in our trimmed files the start date
     is the latest refill, so an earlier visit simply doesn't mention it: silence, not a stop)
   - a stopped medicine is written as "stopped" by the first hospital visited after the stop;
     later hospitals stay silent about it (silence after a stop leaves it stopped)

3. Which traps to plant (up to 2 per patient, picked at random with a fixed seed):
   - stop_one_hospital  The most recently stopped medicine is written as current by the earliest
                        hospital (visit 3 to 14 days before the stop), as stopped by one later
                        hospital, and not mentioned by the other. Right answer: stopped.
   - dose_change        A regular current medicine that at least two hospitals see is written at
                        an earlier dose (half, or double when half would be an odd tablet size) by
                        the earliest of them, and at Synthea's dose by the later ones. Right answer:
                        Synthea's dose, flag dose_changed, old dose in history.
   - allergy_missed     One hospital leaves out one allergy (a drug allergy if there is one).
                        If it was the patient's only allergy, that hospital writes "no known
                        allergies". Right answer: the allergy stays; a conflict if a hospital
                        says no known allergies.
   - silent_medicine    The latest hospital leaves out one current medicine that an earlier
                        hospital recorded (only if the latest hospital still lists another
                        current medicine). Right answer: still current, from the earlier hospital.
   An allergy trap is always tried first when the patient has an allergy, because they are rare.
   If a picked trap can't be planted safely for this patient, the next eligible one is tried.

Every planted trap is a change we made to Synthea's history. Each one is listed, in plain words,
in pipeline/data/traps/<split>_traps.csv (the answer-key format in shared/ has no field for it).

Seed: random.Random(f"{patient_id}-T13-20261114"), so every rerun writes the same records.

Usage (from the repo root, in the project's .venv):
    python pipeline/data/make_hospital_records.py P001 P002 P003 P004 P005
    python pipeline/data/make_hospital_records.py P001 --show      print the three records (working/demo only)
    python pipeline/data/make_hospital_records.py --all-working

Other scripts (the answer-key script, T54) can call written_facts(patient_id) to get the facts each
record states, with exact quotes, without any extra file in the patient folder.

Held-out and reserve patients: this script can write their records (T16), but it only ever prints
their IDs and counts, never their contents (CLAUDE.md, Held-out patients). T13 runs on working only.
"""

import argparse
import csv
import json
import random
import re
import sys
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parent
sys.path.insert(0, str(DATA / "templates"))
import make_records as tpl  # noqa: E402  (the T12 templates)

REFERENCE = date.fromisoformat(tpl.REFERENCE_DATE)
SEED_TAG = "T13-20261114"
TRAPS_DIR = DATA / "traps"
TRAP_COLUMNS = ["patient_id", "trap", "fact_type", "fact_name", "hospitals", "what_we_changed", "right_answer"]
MAX_TRAPS = 2


# ---------- where a patient lives, and whether its contents may be printed ----------

def is_hidden(patient_id):
    # Held-out (P021-P100) and reserve (R...) patients: never print their contents.
    if patient_id.startswith("R"):
        return True
    return patient_id.startswith("P") and int(patient_id[1:]) > 20


def split_of(patient_id):
    if patient_id.startswith("D"):
        return "demo"
    if patient_id.startswith("R"):
        return "reserve"
    return "heldout" if is_hidden(patient_id) else "working"


def patient_folder(patient_id):
    return DATA / split_of(patient_id) / patient_id


def load_trimmed(patient_id):
    path = patient_folder(patient_id) / f"{patient_id}_synthea.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ---------- small date helpers ----------

def d(text):
    return date.fromisoformat(text) if text else None


def iso(day):
    return day.isoformat()


# ---------- step 1: visit dates ----------

def visit_dates(trimmed, rng):
    """Returns {hospital: date} and the order earliest -> latest."""
    order = rng.sample(["A", "B", "C"], 3)                      # earliest, middle, latest
    starts = [d(m["start"]) for m in trimmed["current_medicines"] if m["start"]]
    latest = REFERENCE - timedelta(days=rng.randint(2, 21))
    if starts and max(starts) > latest:
        latest = min(max(starts), REFERENCE)                    # the newest record knows every current medicine
    middle = latest - timedelta(days=rng.randint(30, 120))
    earliest = middle - timedelta(days=rng.randint(90, 365))
    return order, [earliest, middle, latest]


# ---------- step 3a: which traps this patient can take ----------

def dose_change_candidates(trimmed):
    # Single-ingredient medicines with a dose in mg, taken on a regular schedule.
    found = []
    for m in trimmed["current_medicines"]:
        info = tpl.medicine_info(m["description"])
        if "/" in info["generic"] or not re.fullmatch(r"\d+(\.\d+)? mg", info["dose"] or ""):
            continue
        if info["frequency"] in ("", "other", "as_needed", "once"):
            continue
        found.append(m)
    return found


def earlier_dose(dose):
    # "25 mg" -> "12.5 mg"; "2.5 mg" -> "5 mg" (half would be 1.25, an odd tablet size).
    number = float(dose.split(" ")[0])
    half = number / 2
    new = half if round(half, 1) == half and half >= 1 else number * 2
    return f"{new:g} mg"


def stop_candidates(trimmed, latest):
    # A stop needs a later visit to record it, so it must be at least 10 days before the latest visit.
    return [m for m in trimmed["stopped_medicines"] if d(m["last_stop"]) <= latest - timedelta(days=10)]


def eligible_traps(trimmed, latest):
    traps = []
    if stop_candidates(trimmed, latest):
        traps.append("stop_one_hospital")
    if dose_change_candidates(trimmed):
        traps.append("dose_change")
    if [a for a in trimmed["allergies"] if a["active"]]:
        traps.append("allergy_missed")
    if len(trimmed["current_medicines"]) >= 2:
        traps.append("silent_medicine")
    return traps


def pick_traps(trimmed, latest, rng):
    # Every eligible trap, in the order they will be tried: an allergy trap first (they are rare),
    # the rest shuffled. A stop trap is used only if it lands in the first MAX_TRAPS places,
    # because it moves the visit dates and so has to be settled before anything else.
    options = eligible_traps(trimmed, latest)
    picked = ["allergy_missed"] if "allergy_missed" in options else []
    rest = [t for t in options if t not in picked]
    rng.shuffle(rest)
    return picked + rest


# ---------- step 2 + 3: build the three visits ----------

def plan_patient(patient_id):
    """Returns (visits, traps). visits: {hospital: visit dict for the templates}.
    traps: list of rows for the traps file. Same patient, same result, every run."""
    trimmed = load_trimmed(patient_id)
    rng = random.Random(f"{patient_id}-{SEED_TAG}")
    order, dates = visit_dates(trimmed, rng)
    options = pick_traps(trimmed, dates[2], rng)
    traps = options[:MAX_TRAPS]
    rows = []

    # Planned mentions. Each list item: (hospital, entry for the template).
    allergies = {h: [] for h in "ABC"}
    diagnoses = {h: [] for h in "ABC"}
    medicines = {h: [] for h in "ABC"}

    def info_name(desc):
        return tpl.medicine_info(desc)["generic"]

    # Trap 1: stop_one_hospital. Moves the earliest visit to just before the stop.
    stop_trap = None
    if "stop_one_hospital" in traps:
        stop_trap = max(stop_candidates(trimmed, dates[2]), key=lambda m: m["last_stop"])
        stop = d(stop_trap["last_stop"])
        dates[0] = stop - timedelta(days=rng.randint(3, 14))
        if dates[1] <= stop:
            # The middle visit must come after the stop if there is room; else it stays silent before it.
            room = (dates[2] - stop).days
            if room > 8:
                dates[1] = stop + timedelta(days=rng.randint(1, room - 7))
            else:
                dates[1] = dates[0] + timedelta(days=max(1, (stop - dates[0]).days // 2))
    visit = dict(zip(order, dates))
    earliest, middle, latest = order

    # Allergies: every hospital whose visit is on or after the allergy's start.
    for a in trimmed["allergies"]:
        if not a["active"]:
            continue
        for h in "ABC":
            if not a["start"] or d(a["start"]) <= visit[h]:
                allergies[h].append({"synthea_name": a["name"],
                                     "reactions": [r["reaction"] for r in a["reactions"]],
                                     "start": a["start"]})

    # Diagnoses: every hospital whose visit is on or after the start.
    for x in trimmed["diagnoses"]:
        for h in "ABC":
            if not x["start"] or d(x["start"]) <= visit[h]:
                diagnoses[h].append({"description": x["description"], "start": x["start"]})

    # Current medicines: every hospital whose visit is on or after the (latest refill) start.
    for m in trimmed["current_medicines"]:
        for h in "ABC":
            if d(m["start"]) <= visit[h]:
                medicines[h].append({"synthea_description": m["description"], "status": "current",
                                     "date": m["start"]})

    # Stopped medicines (not the trap one): the first hospital visited after the stop says "stopped".
    for m in trimmed["stopped_medicines"]:
        if m is stop_trap:
            continue
        after = [h for h in order if visit[h] >= d(m["last_stop"])]
        if after:
            medicines[after[0]].append({"synthea_description": m["description"], "status": "stopped",
                                        "date": m["last_stop"]})

    # Trap 1 (continued): current at the earliest hospital, stopped at one later one, silent at the other.
    if stop_trap:
        stop = d(stop_trap["last_stop"])
        name = info_name(stop_trap["description"])
        medicines[earliest].append({"synthea_description": stop_trap["description"], "status": "current",
                                    "date": iso(visit[earliest])})
        later = [h for h in (middle, latest) if visit[h] >= stop]
        stopper = rng.choice(later)
        silent = [h for h in (middle, latest) if h != stopper]
        medicines[stopper].append({"synthea_description": stop_trap["description"], "status": "stopped",
                                   "date": stop_trap["last_stop"]})
        rows.append(["stop_one_hospital", "medicine", name, f"{earliest}, {stopper}",
                     f"Hospital {earliest} ({iso(visit[earliest])}) lists {name} as current; "
                     f"Hospital {stopper} records it stopped on {stop_trap['last_stop']}; "
                     f"Hospital {silent[0]} does not mention it. Synthea gives only the stop date, "
                     f"so the current entry at Hospital {earliest} is ours.",
                     f"{name}: stopped ({stop_trap['last_stop']}, Hospital {stopper}); "
                     f"the earlier current entry in history"])

    # Traps 2 to 4, in the picked order. If one can't be planted safely for this patient,
    # the next eligible trap is tried instead, up to MAX_TRAPS in total.
    planted = 1 if stop_trap else 0
    for trap in [t for t in options if t != "stop_one_hospital"]:
        if planted >= MAX_TRAPS:
            break
        row = PLANTERS[trap](rng, trimmed, order, visit, allergies, medicines, rows)
        if row:
            rows.append(row)
            planted += 1

    visits = {}
    for h in "ABC":
        visits[h] = {
            "patient_id": patient_id, "first_name": trimmed["first_name"], "last_name": trimmed["last_name"],
            "birth_date": trimmed["birth_date"], "sex": trimmed["sex"],
            "hospital": h, "visit_date": iso(visit[h]),
            "allergies": allergies[h], "diagnoses": diagnoses[h], "medicines": medicines[h],
        }
    trap_rows = [dict(zip(TRAP_COLUMNS, [patient_id] + r)) for r in rows]
    return visits, trap_rows


# ---------- traps 2 to 4 (trap 1 is inside plan_patient, because it moves the visit dates) ----------

def plant_dose_change(rng, trimmed, order, visit, allergies, medicines, rows):
    # Only a medicine that at least two hospitals really see (visit on or after its start date).
    knows = {}
    for m in dose_change_candidates(trimmed):
        hs = [h for h in order if any(x["synthea_description"] == m["description"] and
                                      x["status"] == "current" for x in medicines[h])]
        if len(hs) >= 2:
            knows[m["description"]] = hs
    if not knows:
        return None
    desc = rng.choice(sorted(knows))
    info = tpl.medicine_info(desc)
    name, today, old = info["generic"], info["dose"], earlier_dose(info["dose"])
    old_h, new_hs = knows[desc][0], knows[desc][1:]
    for x in medicines[old_h]:
        if x["synthea_description"] == desc:
            x["dose"], x["date"] = old, iso(visit[old_h])
    # Hospital A prints a start date. When A has the new dose, that date must come after the
    # old-dose record, so A shows the date of its own visit (the day it saw the new dose).
    if "A" in new_hs:
        for x in medicines["A"]:
            if x["synthea_description"] == desc:
                x["date"] = iso(visit["A"])
    new_words = " and ".join(new_hs)
    verb = "lists" if len(new_hs) == 1 else "list"
    return ["dose_change", "medicine", name, ", ".join([old_h] + new_hs),
            f"Hospital {old_h} ({iso(visit[old_h])}) lists {name} {old}; Hospital {new_words} {verb} "
            f"{today} (Synthea's dose). The {old} entry is ours.",
            f"{name} {today}, current, flag dose_changed, {old} in history"]


def plant_allergy_missed(rng, trimmed, order, visit, allergies, medicines, rows):
    active = [a for a in trimmed["allergies"] if a["active"]]
    drug = [a for a in active if a["category"] == "medication"]
    a = rng.choice(drug or active)
    shown = tpl.allergy_info(a["name"])["name"]
    holders = [h for h in "ABC" if any(x["synthea_name"] == a["name"] for x in allergies[h])]
    if len(holders) < 2:
        return None                                   # needs another hospital that still records it
    h = rng.choice(holders)
    allergies[h] = [x for x in allergies[h] if x["synthea_name"] != a["name"]]
    others = " and ".join(x for x in holders if x != h)
    if allergies[h]:
        what = f"Hospital {h} leaves {shown} out of its allergy list (it lists other allergies). Hospital {others} record it."
        right = f"{shown} allergy stays current (silence never removes an allergy), no conflict"
    else:
        what = f"Hospital {h} writes 'no known allergies'; Hospital {others} record the {shown} allergy."
        right = f"{shown} allergy kept, in a conflict with Hospital {h}'s 'no known allergies'"
    return ["allergy_missed", "allergy", shown, ", ".join(holders), what, right]


def plant_silent_medicine(rng, trimmed, order, visit, allergies, medicines, rows):
    earliest, middle, latest = order
    changed = {r[2] for r in rows}                    # don't hide a medicine another trap uses
    latest_current = [x for x in medicines[latest] if x["status"] == "current"]
    if len(latest_current) < 2:
        return None                                   # the latest hospital must still list another medicine
    def recorded_by(x):
        return [h for h in (earliest, middle) if any(y["synthea_description"] == x["synthea_description"]
                                                     and y["status"] == "current" for y in medicines[h])]
    options = [x for x in latest_current if recorded_by(x)
               and tpl.medicine_info(x["synthea_description"])["generic"] not in changed]
    if not options:
        return None
    x = rng.choice(options)
    name = tpl.medicine_info(x["synthea_description"])["generic"]
    medicines[latest].remove(x)
    earlier = " and ".join(recorded_by(x))
    return ["silent_medicine", "medicine", name, ", ".join(recorded_by(x) + [latest]),
            f"Hospital {latest} (latest visit, {iso(visit[latest])}) does not mention {name}; "
            f"Hospital {earlier} recorded it as current.",
            f"{name} still current, from Hospital {earlier} (silence is not a stop)"]


PLANTERS = {"dose_change": plant_dose_change, "allergy_missed": plant_allergy_missed,
            "silent_medicine": plant_silent_medicine}


# ---------- render, write, and hand facts to the answer-key script ----------

def render_patient(patient_id):
    visits, traps = plan_patient(patient_id)
    records = {h: tpl.render(visits[h]) for h in "ABC"}        # {hospital: (text, facts)}
    return visits, records, traps


def written_facts(patient_id):
    """The facts each record states, in the shape make_answer_key.py reads (for T54)."""
    _, records, _ = render_patient(patient_id)
    out = []
    for h in "ABC":
        text, facts = records[h]
        out.append({"hospital": h, "file": f"{patient_id}{tpl.FILE_ENDINGS[h]}",
                    "facts": [dict(f, flags=[]) for f in facts]})
    return out


def write_patient(patient_id):
    visits, records, traps = render_patient(patient_id)
    folder = patient_folder(patient_id)
    for h in "ABC":
        text, _ = records[h]
        # newline="" keeps the line endings exactly as the template wrote them (same on Windows).
        with (folder / f"{patient_id}{tpl.FILE_ENDINGS[h]}").open("w", encoding="utf-8", newline="") as f:
            f.write(text)
    return visits, records, traps


def update_traps_file(split, new_rows, patient_ids):
    # Keep rows for other patients, replace rows for the patients written in this run.
    TRAPS_DIR.mkdir(exist_ok=True)
    path = TRAPS_DIR / f"{split}_traps.csv"
    rows = []
    if path.exists():
        with path.open(encoding="utf-8", newline="") as f:
            rows = [r for r in csv.DictReader(f) if r["patient_id"] not in patient_ids]
    rows += new_rows
    rows.sort(key=lambda r: r["patient_id"])
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TRAP_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("patients", nargs="*", help="patient IDs, e.g. P001 P002")
    ap.add_argument("--all-working", action="store_true", help="all 20 working patients")
    ap.add_argument("--show", action="store_true", help="also print the records (working and demo only)")
    args = ap.parse_args()

    ids = list(args.patients)
    if args.all_working:
        # The split/ lists hold Synthea's IDs; patients.csv maps them to P001-style IDs.
        with (DATA / "patients.csv").open(encoding="utf-8", newline="") as f:
            ids += [r["patient_id"] for r in csv.DictReader(f) if r["split"] == "working"]
    if not ids:
        ap.error("give patient IDs or --all-working")

    by_split = {}
    for pid in ids:
        visits, records, traps = write_patient(pid)
        by_split.setdefault(split_of(pid), []).append((pid, traps))
        if is_hidden(pid):
            print(f"OK   {pid}: 3 records written, {len(traps)} traps (contents hidden: held-out)")
            continue
        dates = ", ".join(f"{h} {visits[h]['visit_date']}" for h in sorted("ABC", key=lambda h: visits[h]["visit_date"]))
        print(f"OK   {pid}: visits {dates}; traps: {', '.join(t['trap'] for t in traps) or 'none'}")
        if args.show:
            for h in "ABC":
                print(f"----- {pid}{tpl.FILE_ENDINGS[h]} -----")
                print(records[h][0])
    for split, items in by_split.items():
        path = update_traps_file(split, [t for _, ts in items for t in ts], {pid for pid, _ in items})
        print(f"Trap list: {path.relative_to(DATA.parent.parent)}")


if __name__ == "__main__":
    main()
