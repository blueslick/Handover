// Builds the warning banner's lines from a record's facts (T68 items 8-11).
// General rules for any patient (saved runs and live mode alike), no special cases:
// - one line per group of facts where hospitals disagree (conflict_group);
// - any other flag on an allergy or medicine, one line per fact.
// Only allergies and medicines (the critical facts) go in the banner.
import { FLAG_LABELS, FREQUENCY_LABELS, statusLabel } from "./labels";
import { joinWords } from "./dates";
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

  // 2. Any other warning flag on a critical fact.
  for (const f of critical) {
    const other = f.flags.filter((flag) => flag !== "conflict");
    if (other.length === 0) continue;
    lines.push({
      key: `flags-${f.fact_id}`,
      text: `${factName(f)}: ${other.map((flag) => FLAG_LABELS[flag].toLowerCase()).join(", ")}.`,
    });
  }
  return lines;
}
