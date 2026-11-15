// The patient's allergies and medicines in date order (T75 "over time" view).
// Built only from what the merged record already holds: each fact's earlier values
// (history) and its sources. Nothing is guessed. Diagnoses and operations are left
// out to keep the view short; they stay on the doctor screen.
import { FREQUENCY_LABELS, statusLabel } from "./labels";
import { capitalise } from "./names";
import type { Fact, Status } from "./types";

export interface TimelineEvent {
  key: string;
  date: string;
  hospital: string;
  text: string;
  // True for the things a doctor must check: a recorded allergy or a stopped medicine.
  alert: boolean;
}

// One line of words for a fact at one point in time.
function describe(fact: Fact, status: Status, dose: string | null, frequency: string | null): string {
  const name = capitalise(fact.name ?? fact.name_as_written ?? "No name recorded");
  if (status === "none_recorded") return `${statusLabel({ type: fact.type, status })} stated`;
  if (fact.type === "allergy") {
    return status === "current" ? `${name} allergy recorded` : `${name}: ${statusLabel({ type: fact.type, status }).toLowerCase()}`;
  }
  if (status === "current") {
    const how = [dose, frequency && (FREQUENCY_LABELS[frequency] ?? frequency)].filter(Boolean).join(", ");
    return how ? `${name} ${how}` : name;
  }
  return `${name} ${statusLabel({ type: fact.type, status }).toLowerCase()}`;
}

export function timelineEvents(facts: Fact[]): TimelineEvent[] {
  const events: TimelineEvent[] = [];
  for (const f of facts) {
    if (f.type !== "allergy" && f.type !== "medicine") continue;
    // Earlier values of this fact.
    f.history.forEach((h, i) =>
      events.push({
        key: `${f.fact_id}-h${i}`,
        date: h.date,
        hospital: h.hospital,
        text: describe(f, h.status, h.dose, h.frequency),
        alert: f.type === "medicine" && h.status === "stopped",
      }),
    );
    const alert = (f.type === "allergy" && (f.status === "current" || f.status === "suspected")) || (f.type === "medicine" && f.status === "stopped");
    if (f.status === "none_recorded" && f.sources.length > 0) {
      // "No known allergies": one line for each hospital that said it.
      f.sources.forEach((s, i) =>
        events.push({ key: `${f.fact_id}-s${i}`, date: s.date, hospital: s.hospital, text: describe(f, f.status, null, null), alert: false }),
      );
      continue;
    }
    // The value now: dated from the first record that states it (a stop keeps its own date).
    const first = f.status === "stopped" ? null : [...f.sources].sort((a, b) => (a.date < b.date ? -1 : 1))[0];
    events.push({
      key: `${f.fact_id}-now`,
      date: first?.date ?? f.date,
      hospital: first?.hospital ?? f.hospital,
      text: describe(f, f.status, f.dose, f.frequency),
      alert,
    });
  }
  // Plain YYYY-MM-DD dates sort correctly as text.
  return events.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
}

// For the right-hand panel: each hospital's most recent date and how many facts mention it.
export function hospitalEntries(facts: Fact[]): { hospital: string; latest: string | null; facts: number }[] {
  const map = new Map<string, { latest: string | null; ids: Set<string> }>();
  for (const f of facts) {
    const places = [{ hospital: f.hospital, date: f.date }, ...f.sources, ...f.history];
    for (const p of places) {
      if (!p.hospital) continue;
      const e = map.get(p.hospital) ?? { latest: null, ids: new Set<string>() };
      e.ids.add(f.fact_id);
      if (p.date && /^\d{4}-\d{2}-\d{2}$/.test(p.date) && (e.latest === null || p.date > e.latest)) e.latest = p.date;
      map.set(p.hospital, e);
    }
  }
  return [...map.entries()].sort(([a], [b]) => (a < b ? -1 : 1)).map(([hospital, e]) => ({ hospital, latest: e.latest, facts: e.ids.size }));
}
