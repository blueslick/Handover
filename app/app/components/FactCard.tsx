// One card for one fact: the fact, its status as a word, hospital and date,
// the source quote, and any warning. Nothing here relies on colour alone.
import { FLAG_LABELS, FREQUENCY_LABELS, statusLabel } from "@/lib/labels";
import type { Fact } from "@/lib/types";
import { doseChange, factAnchor } from "@/lib/banner";
import { statusStyle } from "@/lib/statusStyle";
import { factName } from "@/lib/names";
import Quote, { quoteTerms } from "./Quote";
// T68 item 16: dates as "5 Oct 2021", not "2021-10-05".
import { formatDate } from "@/lib/dates";

// Builds the headline.
// T68 item 12: a "nothing recorded" line is titled by its status in words
// ("No known allergies"), never by the shorthand it was written in ("NKA"),
// which stays visible inside the quote.
// T68 item 14: generic name first, with a capital, and the brand after it, e.g.
// "Metformin (written as Glucophage at Hospital C)". Same name rule as the banner.
function headline(fact: Fact): string {
  const name = factName(fact);
  const written = fact.name_as_written ?? "";
  if (fact.status !== "none_recorded" && fact.name && written && written.toLowerCase() !== fact.name.toLowerCase()) {
    return `${name} (written as ${written} at Hospital ${fact.hospital})`;
  }
  return name;
}

// Dose, frequency and reaction, joined into one line when present.
// T68 item 15: when the dose changed, the old and new dose sit on one line:
// "500 mg → 1000 mg, twice a day".
function details(fact: Fact): string {
  const parts: string[] = [];
  const change = fact.flags.includes("dose_changed") ? doseChange(fact) : null;
  if (change) {
    parts.push(change.sameFreq ? `${change.from} → ${fact.dose}` : `${change.from} → ${change.to}`);
    if (change.sameFreq && fact.frequency) parts.push(FREQUENCY_LABELS[fact.frequency] ?? fact.frequency);
  } else {
    if (fact.dose) parts.push(fact.dose);
    if (fact.frequency) parts.push(FREQUENCY_LABELS[fact.frequency] ?? fact.frequency);
  }
  if (fact.reaction) parts.push(`reaction: ${fact.reaction}`);
  return parts.join(", ");
}

export default function FactCard({ fact }: { fact: Fact }) {
  const detail = details(fact);
  const style = statusStyle(fact);
  // Other hospitals that state the same current value (the latest one is shown above).
  const otherSources = fact.sources.filter(
    (s) => !(s.hospital === fact.hospital && s.date === fact.date && s.quote === fact.quote),
  );

  return (
    <article id={factAnchor(fact.fact_id)} className={`scroll-mt-4 rounded p-4 flex-1 min-w-0 ${style.card}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className={`text-lg font-semibold break-words ${style.struck ? "line-through decoration-2" : ""}`}>
          {headline(fact)}
        </h3>
        <span className={`rounded px-2 py-0.5 text-sm font-semibold ${style.pill}`}>
          Status: {statusLabel(fact)}
        </span>
      </div>

      {detail && <p className="mt-1 text-zinc-800">{detail}</p>}

      {/* T68 item 18: each part of the card is labelled in words. */}
      <p className="mt-2 text-sm text-zinc-700">
        <span className="font-medium">Latest source:</span> Hospital {fact.hospital}, {formatDate(fact.date)}
      </p>
      <blockquote className="mt-1 border-l-4 border-zinc-400 pl-3 text-sm italic break-words">
        <Quote text={fact.quote} file={fact.sources.find((s) => s.quote === fact.quote)?.file} terms={quoteTerms(fact)} />
      </blockquote>

      {otherSources.length > 0 && (
        <div className="mt-2 text-sm text-zinc-700">
          <p className="font-medium">Also stated by:</p>
          <ul className="list-disc pl-5">
            {otherSources.map((s) => (
              <li key={`${s.file}-${s.date}`} className="break-words">
                Hospital {s.hospital}, {formatDate(s.date)}: <Quote text={s.quote} file={s.file} terms={quoteTerms(fact)} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {fact.history.length > 0 && (
        <div className="mt-2 text-sm text-zinc-700">
          <p className="font-medium">Earlier (older values of this fact):</p>
          <ul className="list-disc pl-5">
            {fact.history.map((h) => (
              <li key={`${h.hospital}-${h.date}`} className="break-words">
                {[statusLabel({ type: fact.type, status: h.status }), h.dose, h.frequency && (FREQUENCY_LABELS[h.frequency] ?? h.frequency)]
                  .filter(Boolean)
                  .join(", ")}{" "}
                (Hospital {h.hospital}, {formatDate(h.date)}): <Quote text={h.quote} terms={quoteTerms(fact, h.dose)} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {fact.flags.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-2">
          {fact.flags.map((flag) => (
            <li
              key={flag}
              className="border-2 border-amber-700 bg-amber-50 text-amber-950 rounded px-2 py-0.5 text-sm font-semibold"
            >
              Warning: {FLAG_LABELS[flag]}
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
