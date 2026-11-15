// How the baseline differs from Handover for one patient (T68 item 22).
// Worked out from the two records each time, never typed in, so it is right for any
// patient, including live runs. Only allergies and medicines (the critical facts).
import { formatDate } from "./dates";
import { capitalise } from "./names";
import type { CompiledRecord, Fact } from "./types";

const critical = (f: Fact) => f.type === "allergy" || f.type === "medicine";
const key = (f: Fact) => `${f.type}:${(f.name ?? "").toLowerCase()}`;

// "1 g" and "1000 mg" are the same dose; compare doses in mg where possible.
function normDose(d: string | null): string | null {
  if (!d) return null;
  const m = /^(\d+(?:\.\d+)?)\s*(mg|g|mcg)$/i.exec(d.trim());
  if (!m) return d.trim().toLowerCase();
  const n = Number(m[1]);
  const unit = m[2].toLowerCase();
  if (unit === "g") return `${n * 1000} mg`;
  return `${n} ${unit}`;
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

export function baselineDifferences(handover: CompiledRecord, baseline: CompiledRecord): string[] {
  const out: string[] = [];
  const h = handover.facts.filter(critical).filter((f) => f.name);
  const b = baseline.facts.filter(critical).filter((f) => f.name);
  const bBy = new Map<string, Fact[]>();
  for (const f of b) bBy.set(key(f), [...(bBy.get(key(f)) ?? []), f]);
  const hKeys = new Set(h.map(key));

  // 1. Stopped medicines that the baseline still lists as current: the main harm.
  for (const f of h.filter((x) => x.type === "medicine" && x.status === "stopped")) {
    const cur = (bBy.get(key(f)) ?? []).filter((x) => x.status === "current");
    if (cur.length > 0) {
      out.push(
        `Lists ${f.name} as current (${plural(cur.length, "entry", "entries")}), though Hospital ${f.hospital} recorded it stopped on ${formatDate(f.date)}.`,
      );
    }
  }

  // 2. The same drug or allergy repeated, with how many different doses.
  for (const [k, list] of bBy) {
    if (list.length < 2) continue;
    const name = list[0].name!;
    const doses = new Set(list.map((x) => normDose(x.dose)).filter(Boolean));
    const doseText = list[0].type === "medicine" && doses.size > 1 ? ` with ${doses.size} different doses` : "";
    // Skip if this was already said as a stopped medicine above.
    if (out.some((line) => line.startsWith(`Lists ${name} as current`)) && doseText === "") continue;
    out.push(`Shows ${name} ${list.length} times${doseText}.`);
    void k;
  }

  // 3. Disagreements between hospitals that the baseline does not show.
  const groups = new Map<string, Fact[]>();
  for (const f of h) if (f.conflict_group) groups.set(f.conflict_group, [...(groups.get(f.conflict_group) ?? []), f]);
  const baselineHasConflicts = b.some((f) => f.conflict_group);
  if (groups.size > 0 && !baselineHasConflicts) {
    const types = [...new Set([...groups.values()].map((g) => (g[0].type === "allergy" ? "allergies" : "medicines")))];
    out.push(`Does not show that hospitals disagree on ${types.join(" and ")}.`);
  }

  // 4. Facts Handover lists that the baseline misses, and the other way round.
  const missing = [...new Set(h.filter((f) => !bBy.has(key(f))).map((f) => f.name!))];
  if (missing.length > 0) out.push(`Does not list: ${missing.join(", ")}.`);
  const extra = [...new Set(b.filter((f) => !hKeys.has(key(f))).map((f) => f.name!))];
  if (extra.length > 0) out.push(`Lists names Handover does not: ${extra.join(", ")}.`);

  // 5. Stopped medicines or dose changes it cannot mark at all.
  const hasStatusWords = b.some((f) => f.status !== "current");
  if (!hasStatusWords && h.some((f) => f.status === "stopped")) {
    out.push("Marks every entry as current: it has no way to show a stopped medicine.");
  }
  return out.map((s) => capitalise(s));
}
