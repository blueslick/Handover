// Builds the warning banner's lines from a record's facts (T68 items 8-11).
// General rules for any patient (saved runs and live mode alike), no special cases:
// - one line per group of facts where hospitals disagree (conflict_group);
// - one line per stopped medicine;
// - one line per dose change, old and new dose in full;
// - any other flag on an allergy or medicine, one line per fact.
// Only allergies and medicines (the critical facts) go in the banner.
import { FLAG_LABELS, FREQUENCY_LABELS, statusLabel } from "./labels";
import { formatDate, joinWords } from "./dates";
import { factHospitals, factName } from "./names";
import type { Fact } from "./types";

export interface BannerLine {
  key: string;
  text: string;
}

const isCritical = (f: Fact) => f.type === "allergy" || f.type === "medicine";

// "Hospital A" or "Hospitals B and C".
function hospitalsPhrase(hs: string[]): string {
  return `Hospital${hs.length > 1 ? "s" : ""} ${joinWords(hs)}`;
}

// One side of a disagreement, e.g. "Hospital A records penicillin (skin rash)" or
// "Hospitals B and C say no known allergies".
function conflictSide(f: Fact): string {
  const hs = factHospitals(f);
  const who = hospitalsPhrase(hs);
  if (f.status === "none_recorded") {
    return `${who} ${hs.length > 1 ? "say" : "says"} ${statusLabel(f).toLowerCase()}`;
  }
  const name = (f.name ?? f.name_as_written ?? "no name recorded").toLowerCase();
  const dose = [f.dose, f.frequency && (FREQUENCY_LABELS[f.frequency] ?? f.frequency)].filter(Boolean).join(" ");
  const extra = f.reaction ? ` (${f.reaction})` : "";
  const status = f.status === "current" ? "" : `, ${statusLabel(f).toLowerCase()}`;
  return `${who} ${hs.length > 1 ? "record" : "records"} ${name}${dose ? ` ${dose}` : ""}${extra}${status}`;
}

const freq = (x: string | null) => (x ? (FREQUENCY_LABELS[x] ?? x) : "");

// The old and new dose, in words. The frequency is said once when it did not change
// ("500 mg to 1000 mg twice a day") and on both sides when it did.
export function doseChange(f: Fact): { from: string; to: string } | null {
  const earlier = [...f.history]
    .filter((h) => h.dose && h.dose !== f.dose)
    .sort((a, b) => (a.date < b.date ? -1 : 1))
    .pop();
  if (!earlier || !f.dose) return null;
  const sameFreq = (earlier.frequency ?? "") === (f.frequency ?? "");
  const from = sameFreq ? earlier.dose! : [earlier.dose, freq(earlier.frequency)].filter(Boolean).join(" ");
  const to = [f.dose, freq(f.frequency)].filter(Boolean).join(" ");
  return { from, to };
}

export function bannerLines(facts: Fact[]): BannerLine[] {
  const lines: BannerLine[] = [];
  const critical = facts.filter(isCritical);

  // 1. Disagreements: one line per conflict group, every side shown, none ranked first.
  const seen = new Set<string>();
  for (const f of critical) {
    if (!f.conflict_group || seen.has(f.conflict_group)) continue;
    seen.add(f.conflict_group);
    const group = critical.filter((g) => g.conflict_group === f.conflict_group);
    const type = f.type === "allergy" ? "Allergy" : "Medicine";
    lines.push({
      key: `conflict-${f.conflict_group}`,
      text: `${type}, hospitals disagree: ${group.map(conflictSide).join(". ")}.`,
    });
  }

  // 2. Stopped medicines (T68 item 9): a stopped drug that someone keeps giving is the
  // main harm this tool is for. Says when an older record still lists it as current.
  for (const f of critical) {
    if (f.type !== "medicine" || f.status !== "stopped" || f.conflict_group) continue;
    const olderCurrent = f.history.some((h) => h.status === "current");
    lines.push({
      key: `stopped-${f.fact_id}`,
      text:
        `${factName(f)}: stopped ${formatDate(f.date)} (Hospital ${f.hospital}).` +
        (olderCurrent ? " An older record lists it as current." : ""),
    });
  }

  // 3. Dose changes (T68 item 10), written in full: "Metformin: dose changed from
  // 500 mg to 1000 mg twice a day." The old dose is the latest earlier entry whose dose
  // differs from today's.
  for (const f of critical) {
    if (!f.flags.includes("dose_changed")) continue;
    const change = doseChange(f);
    lines.push({
      key: `dose-${f.fact_id}`,
      text: change
        ? `${factName(f)}: dose changed from ${change.from} to ${change.to}.`
        : `${factName(f)}: dose changed (the earlier dose is not recorded).`,
    });
  }

  // 4. Any other warning flag on a critical fact (conflicts and dose changes are above).
  for (const f of critical) {
    const other = f.flags.filter((flag) => flag !== "conflict" && flag !== "dose_changed");
    if (other.length === 0) continue;
    lines.push({
      key: `flags-${f.fact_id}`,
      text: `${factName(f)}: ${other.map((flag) => FLAG_LABELS[flag].toLowerCase()).join(", ")}.`,
    });
  }
  return lines;
}
