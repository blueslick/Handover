// Which hospitals a record's facts came from, and the latest date written in any of
// them (T68 item 7). The record format has no visit date, so this is the most recent
// date attached to any fact or source, and the page says so in those words.
import type { Fact } from "./types";

export interface SourcesSummary {
  hospitals: string[];
  latestDate: string | null;
  latestHospital: string | null;
}

export function summariseSources(facts: Fact[]): SourcesSummary {
  const hospitals = new Set<string>();
  let latestDate: string | null = null;
  let latestHospital: string | null = null;
  // Every place a fact was read from: its sources, its history, and the fact itself.
  const places = facts.flatMap((f) => [
    { hospital: f.hospital, date: f.date },
    ...f.sources.map((s) => ({ hospital: s.hospital, date: s.date })),
    ...f.history.map((h) => ({ hospital: h.hospital, date: h.date })),
  ]);
  for (const p of places) {
    if (p.hospital) hospitals.add(p.hospital);
    // Plain YYYY-MM-DD dates compare correctly as text.
    if (p.date && /^\d{4}-\d{2}-\d{2}$/.test(p.date) && (latestDate === null || p.date > latestDate)) {
      latestDate = p.date;
      latestHospital = p.hospital;
    }
  }
  return { hospitals: [...hospitals].sort(), latestDate, latestHospital };
}
