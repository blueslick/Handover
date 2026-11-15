// Builds the "Check first" lines from a record's facts (T68 items 8-11, reworded in T81).
// General rules for any patient (saved runs and live mode alike), no special cases:
// - one line per group of facts where hospitals disagree (conflict_group);
// - one line per stopped medicine;
// - one line per dose change, old and new dose in full;
// - any other flag on an allergy or medicine, one line per fact.
// Only allergies and medicines (the critical facts) go in the list.
// T81: each line is a short full sentence that names the hospitals, and carries a short
// label ("Hospitals disagree", "Dose changed") shown beside it.
import { FLAG_LABELS, FREQUENCY_LABELS, statusLabel } from "./labels";
import { formatDate, joinWords } from "./dates";
import { hospitalShort } from "./hospitals";
import { factHospitals, factName } from "./names";
import type { Fact } from "./types";

export interface BannerLine {
  key: string;
  // The short label shown beside the sentence, e.g. "Hospitals disagree".
  label: string;
  text: string;
  // The id of the row the line jumps to.
  target: string;
}

// Page ids for rows and conflict boxes, used by the "Go to row" links and FactList.
export const factAnchor = (factId: string) => `fact-${factId}`;
export const conflictAnchor = (group: string) => `conflict-${group}`;

const isCritical = (f: Fact) => f.type === "allergy" || f.type === "medicine";

// "Northfield" or "Riverside and Seri Bayu".
const hospitalsPhrase = (hs: string[]) => joinWords(hs.map(hospitalShort));

// One side of a disagreement as a sentence, e.g. "Penicillin allergy recorded at Northfield."
// or "No known allergies at Riverside and Seri Bayu."
function conflictSide(f: Fact): string {
  const where = hospitalsPhrase(factHospitals(f));
  if (f.status === "none_recorded") return `${statusLabel(f)} at ${where}.`;
  const name = factName(f);
  if (f.type === "allergy") {
    const kind = f.status === "current" ? "allergy" : statusLabel(f).toLowerCase();
    return `${name} ${kind} recorded at ${where}.`;
  }
  const dose = [f.dose, f.frequency && (FREQUENCY_LABELS[f.frequency] ?? f.frequency)].filter(Boolean).join(" ");
  const status = f.status === "current" ? "" : ` (${statusLabel(f).toLowerCase()})`;
  return `${name}${dose ? ` ${dose}` : ""}${status} at ${where}.`;
}

const freq = (x: string | null) => (x ? (FREQUENCY_LABELS[x] ?? x) : "");

// The old and new dose, in words. The frequency is said once when it did not change
// ("500 mg to 1000 mg twice a day") and on both sides when it did.
export function doseChange(f: Fact): { from: string; to: string; sameFreq: boolean } | null {
  const earlier = [...f.history]
    .filter((h) => h.dose && h.dose !== f.dose)
    .sort((a, b) => (a.date < b.date ? -1 : 1))
    .pop();
  if (!earlier || !f.dose) return null;
  const sameFreq = (earlier.frequency ?? "") === (f.frequency ?? "");
  const from = sameFreq ? earlier.dose! : [earlier.dose, freq(earlier.frequency)].filter(Boolean).join(" ");
  const to = [f.dose, freq(f.frequency)].filter(Boolean).join(" ");
  return { from, to, sameFreq };
}

// The hospitals whose older record still lists a now-stopped medicine as current.
export function stillListedAt(f: Fact): string[] {
  if (f.type !== "medicine" || f.status !== "stopped") return [];
  return [...new Set(f.history.filter((h) => h.status === "current" && h.hospital !== f.hospital).map((h) => h.hospital))].sort();
}

// The short labels for one row's Check column (T81). Empty when there is nothing to check.
// A stopped medicine that another hospital's record still lists counts as a disagreement
// between hospitals (Daniel, 15 Nov).
export function checkLabels(f: Fact): string[] {
  const labels: string[] = [];
  if (f.conflict_group || f.flags.includes("conflict") || stillListedAt(f).length > 0) labels.push(FLAG_LABELS.conflict);
  for (const flag of f.flags) {
    if (flag === "conflict") continue;
    labels.push(FLAG_LABELS[flag]);
  }
  return labels;
}

export function bannerLines(facts: Fact[]): BannerLine[] {
  const lines: BannerLine[] = [];
  const critical = facts.filter(isCritical);

  // 1. Disagreements: one line per conflict group, every side said, none ranked first.
  // The side that records something comes before the side that says "none".
  const seen = new Set<string>();
  for (const f of critical) {
    if (!f.conflict_group || seen.has(f.conflict_group)) continue;
    seen.add(f.conflict_group);
    const group = critical.filter((g) => g.conflict_group === f.conflict_group);
    const sides = [...group.filter((g) => g.status !== "none_recorded"), ...group.filter((g) => g.status === "none_recorded")];
    lines.push({
      key: `conflict-${f.conflict_group}`,
      label: FLAG_LABELS.conflict,
      target: conflictAnchor(f.conflict_group),
      text: sides.map(conflictSide).join(" "),
    });
  }

  // 2. Stopped medicines (T68 item 9): a stopped drug that someone keeps giving is the
  // main harm this tool is for. Says which hospital's older record still lists it.
  for (const f of critical) {
    if (f.type !== "medicine" || f.status !== "stopped" || f.conflict_group) continue;
    const still = stillListedAt(f);
    lines.push({
      key: `stopped-${f.fact_id}`,
      label: still.length > 0 ? FLAG_LABELS.conflict : "Stopped medicine",
      target: factAnchor(f.fact_id),
      text:
        `${factName(f)} stopped at ${hospitalShort(f.hospital)} on ${formatDate(f.date)}.` +
        (still.length > 0 ? ` ${hospitalsPhrase(still)} still ${still.length > 1 ? "list" : "lists"} it.` : ""),
    });
  }

  // 3. Dose changes (T68 item 10), written in full: "Metformin dose changed from 500 mg
  // to 1000 mg twice a day." The old dose is the latest earlier entry whose dose differs.
  for (const f of critical) {
    if (!f.flags.includes("dose_changed")) continue;
    const change = doseChange(f);
    lines.push({
      key: `dose-${f.fact_id}`,
      label: FLAG_LABELS.dose_changed,
      target: f.conflict_group ? conflictAnchor(f.conflict_group) : factAnchor(f.fact_id),
      text: change ? `${factName(f)} dose changed from ${change.from} to ${change.to}.` : `${factName(f)} dose changed. The earlier dose is not recorded.`,
    });
  }

  // 4. Any other warning flag on a critical fact (conflicts and dose changes are above).
  for (const f of critical) {
    for (const flag of f.flags) {
      if (flag === "conflict" || flag === "dose_changed") continue;
      lines.push({
        key: `${flag}-${f.fact_id}`,
        label: FLAG_LABELS[flag],
        target: f.conflict_group ? conflictAnchor(f.conflict_group) : factAnchor(f.fact_id),
        text: `${factName(f)}: ${FLAG_LABELS[flag].toLowerCase()}.`,
      });
    }
  }
  return lines;
}
