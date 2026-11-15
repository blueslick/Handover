// A source quote, word for word (T68 item 17). Nothing in the text is changed: it is
// only split into pieces so the parts that match the fact (drug name, dose, status)
// can be highlighted. Rows from a table (CSV) file are shown in a fixed-width font,
// because a comma-separated row is hard to read in italics.
import type { Fact } from "@/lib/types";

// Words that show a status in the hospital records' own wording.
const STATUS_WORDS = ["Active", "Inactive", "Stopped", "stopped", "Resolved", "no known allergies", "NKA", "no regular medicines"];

// The words to look for in a quote about this fact.
export function quoteTerms(fact: Pick<Fact, "name" | "name_as_written" | "dose" | "reaction">, dose?: string | null): string[] {
  const terms: string[] = [...STATUS_WORDS];
  if (fact.name_as_written) terms.push(fact.name_as_written);
  if (fact.name) terms.push(fact.name, ...fact.name.split(" / "));
  for (const d of [dose ?? fact.dose]) {
    if (!d) continue;
    terms.push(d);
    // "1000 mg" is often written "1 g" in the records.
    const mg = /^(\d+(?:\.\d+)?) mg$/.exec(d);
    if (mg && Number(mg[1]) >= 1000 && Number(mg[1]) % 1000 === 0) terms.push(`${Number(mg[1]) / 1000} g`);
  }
  if (fact.reaction) terms.push(fact.reaction);
  return terms.filter((t) => t.trim().length >= 2);
}

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

// Splits the text into plain and highlighted pieces; joining them gives the text back exactly.
function pieces(text: string, terms: string[]): { text: string; hit: boolean }[] {
  const sorted = [...new Set(terms)].sort((a, b) => b.length - a.length);
  if (sorted.length === 0) return [{ text, hit: false }];
  // Whole words only, so "iron" does not light up inside another word.
  const pattern = sorted.map((t) => `(?<![A-Za-z0-9])${escape(t)}(?![A-Za-z0-9])`).join("|");
  const re = new RegExp(pattern, "gi");
  const out: { text: string; hit: boolean }[] = [];
  let last = 0;
  for (const m of text.matchAll(re)) {
    const at = m.index ?? 0;
    if (at > last) out.push({ text: text.slice(last, at), hit: false });
    out.push({ text: m[0], hit: true });
    last = at + m[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last), hit: false });
  return out;
}

export function isTableRow(text: string, file?: string | null): boolean {
  return Boolean(file?.toLowerCase().endsWith(".csv")) || (text.match(/,/g)?.length ?? 0) >= 4;
}

export default function Quote({ text, file, terms }: { text: string; file?: string | null; terms: string[] }) {
  const table = isTableRow(text, file);
  return (
    <span className={table ? "font-mono not-italic text-[0.85em] break-all" : ""}>
      “
      {pieces(text, terms).map((p, i) =>
        p.hit ? (
          <mark key={i} className="bg-yellow-200 text-ink rounded-sm px-0.5 font-medium">
            {p.text}
          </mark>
        ) : (
          <span key={i}>{p.text}</span>
        ),
      )}
      ”
    </span>
  );
}
