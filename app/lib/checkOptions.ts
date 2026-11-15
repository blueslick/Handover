// "Ways to check this" (T80): for every warning, the options a doctor has for checking it,
// gathered in one place so no time goes on looking them up in an emergency.
// Each warning gets two things:
//   shows    what the merged record did with the fact (a statement about the tool);
//   options  who or what could confirm it: the patient, the medicine's box, and every
//            hospital whose record mentions the fact, with what that record says, its
//            date, and that hospital's contact.
// Rules for the wording (CLAUDE.md app rules and the "not medical advice" line):
//   - options only: no order, no "first", no "should", and nothing about what to prescribe
//     or which record to rely on. The doctor decides;
//   - it never picks a winner between two hospitals: both records stay on the screen;
//   - what a hospital "says" is only what is already in the merged record (names, doses,
//     statuses, dates), which the tool read from that hospital's own words.
// Display only: nothing here changes a record, a score or the tested tool.
import { FREQUENCY_LABELS, statusLabel } from "./labels";
import { doseChange } from "./banner";
import { formatDate } from "./dates";
import { factName } from "./names";
import type { Fact, Flag } from "./types";

export interface CheckOption {
  who: string;
  // What that hospital's record says, from the merged record. Empty for the patient.
  detail?: string;
  // A hospital letter adds that hospital's example contact.
  hospital?: string;
}

export interface CheckPlan {
  key: string;
  // Which warning the plan is about, e.g. "Dose not recorded".
  title: string;
  shows: string;
  options: CheckOption[];
}

const lower = (s: string) => s.toLowerCase();
const doseWords = (dose: string | null, frequency: string | null) => [dose, frequency && (FREQUENCY_LABELS[frequency] ?? frequency)].filter(Boolean).join(" ");

// "metformin 1000 mg twice a day" / "an allergy to penicillin (reaction: skin rash)".
function factWords(f: Fact): string {
  const name = lower(f.name ?? f.name_as_written ?? "an item with no name recorded");
  const dose = doseWords(f.dose, f.frequency);
  const words = `${name}${dose ? ` ${dose}` : ""}${f.reaction ? ` (reaction: ${f.reaction})` : ""}`;
  return f.type === "allergy" ? `an allergy to ${words}` : words;
}

// Options that are not a hospital. No instruction is attached: they are simply listed.
const PATIENT: CheckOption = { who: "The patient, a family member or a carer" };
const BOX: CheckOption = { who: "The medicine's box or label" };

// One option per hospital whose record states this fact: what it says and the date it gives.
function sourceOptions(f: Fact): CheckOption[] {
  const out: CheckOption[] = [];
  for (const s of [...f.sources].sort((a, b) => a.hospital.localeCompare(b.hospital))) {
    if (out.some((o) => o.hospital === s.hospital)) continue;
    const status = f.status === "current" ? "" : `, ${lower(statusLabel(f))}`;
    out.push({
      who: `Hospital ${s.hospital}`,
      hospital: s.hospital,
      detail: f.status === "none_recorded" ? `Its record says "${lower(statusLabel(f))}", dated ${formatDate(s.date)}.` : `Its record lists ${factWords(f)}${status}, dated ${formatDate(s.date)}.`,
    });
  }
  return out;
}

// One option per hospital whose earlier record gave a different value (not already listed).
function historyOptions(f: Fact, already: CheckOption[]): CheckOption[] {
  const out: CheckOption[] = [];
  for (const h of f.history) {
    if ([...already, ...out].some((o) => o.hospital === h.hospital)) continue;
    const was = [lower(statusLabel({ type: f.type, status: h.status })), doseWords(h.dose, h.frequency)].filter(Boolean).join(", ");
    out.push({ who: `Hospital ${h.hospital}`, hospital: h.hospital, detail: `Its earlier record, dated ${formatDate(h.date)}, gave: ${was}.` });
  }
  return out;
}

// The plan for one group of facts where hospitals disagree.
export function conflictPlan(group: Fact[]): CheckPlan {
  // The side that records something first, then the side that says "none"; neither is ranked.
  const sides = [...group.filter((f) => f.status !== "none_recorded"), ...group.filter((f) => f.status === "none_recorded")];
  const hospitals: CheckOption[] = [];
  for (const f of sides) for (const o of sourceOptions(f)) if (!hospitals.some((x) => x.hospital === o.hospital)) hospitals.push(o);
  return {
    key: `conflict-${group[0].conflict_group}`,
    title: "Hospitals disagree",
    shows: "Both lines are kept on this record. The tool does not remove either one and does not choose between them.",
    options: [PATIENT, ...(group[0].type === "medicine" ? [BOX] : []), ...hospitals],
  };
}

// What the merged record did, for each warning on a single fact.
const FLAG_SHOWS: Partial<Record<Flag, { title: string; shows: (f: Fact) => string }>> = {
  missing_dose: {
    title: "Dose not recorded",
    shows: (f) => `No hospital record gives a dose for ${lower(factName(f))}. The tool does not guess one, so none is shown.`,
  },
  dose_changed: {
    title: "Dose changed",
    shows: (f) => {
      const change = doseChange(f);
      return change
        ? `The latest dated record gives ${change.to}; an earlier record gave ${change.from}. The latest dated dose is shown and the earlier one is kept under "Earlier".`
        : "The dose differs from an earlier record. The latest dated dose is shown.";
    },
  },
  unverified: {
    title: "Not verified against the source",
    shows: () => "The tool could not match this line to the hospital record's own words. The line is kept and marked, not removed.",
  },
  unknown_name: {
    title: "Unknown drug name",
    shows: (f) => `The name is shown exactly as written${f.name_as_written ? ` ("${f.name_as_written}")` : ""}. It is not in the tool's medicine list, so no standard name is shown.`,
  },
};

// The plans for one fact's own warnings. A disagreement is handled per group, above.
export function factPlans(f: Fact): CheckPlan[] {
  return f.flags.flatMap((flag) => {
    const entry = FLAG_SHOWS[flag];
    if (!entry) return [];
    const sources = sourceOptions(f);
    return [
      {
        key: `${flag}-${f.fact_id}`,
        title: entry.title,
        shows: entry.shows(f),
        options: [PATIENT, ...(f.type === "medicine" ? [BOX] : []), ...sources, ...historyOptions(f, sources)],
      },
    ];
  });
}

