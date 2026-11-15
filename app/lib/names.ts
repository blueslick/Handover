// How a fact's name is shown (T68). The generic name comes first, with a capital
// letter, so the same medicine looks the same on every card and in the banner.
import { statusLabel } from "./labels";
import type { Fact } from "./types";

export function capitalise(s: string): string {
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}

// The name as a label: "Metformin", or for a "nothing recorded" line its status in words
// ("No known allergies"), or the words as written if there is no generic name.
export function factName(fact: Pick<Fact, "type" | "status" | "name" | "name_as_written">): string {
  if (fact.status === "none_recorded") return statusLabel(fact);
  if (fact.name) return capitalise(fact.name);
  return fact.name_as_written || "No name recorded";
}

// The hospitals a fact was read from, in letter order (its sources, or its own hospital).
export function factHospitals(fact: Pick<Fact, "hospital" | "sources">): string[] {
  const set = new Set(fact.sources.map((s) => s.hospital));
  if (set.size === 0 && fact.hospital) set.add(fact.hospital);
  return [...set].sort();
}
