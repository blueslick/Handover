// Where one fact came from (T75), shown in the right-hand panel when its line is tapped:
// the latest source and its quote word for word, every other hospital that says the same,
// the earlier values, and any warning. This is the "fact card" of the Minimal look.
import { factPlans } from "@/lib/checkOptions";
import { FLAG_LABELS, FREQUENCY_LABELS, statusLabel } from "@/lib/labels";
import { formatDate } from "@/lib/dates";
import { factName } from "@/lib/names";
import type { Fact } from "@/lib/types";
import CheckOptionsBox from "./CheckOptionsBox";
import { factDetail } from "./FactRow";
import Quote, { quoteTerms } from "./Quote";

// headingId lets the panel appear twice on a page (in the right-hand panel on a laptop,
// under the tapped line on a phone) without two parts sharing one id.
export default function SourcePanel({ fact, headingId = "source-heading" }: { fact: Fact; headingId?: string }) {
  const others = fact.sources.filter((s) => !(s.hospital === fact.hospital && s.date === fact.date && s.quote === fact.quote));
  const written = fact.name_as_written ?? "";
  const renamed = fact.status !== "none_recorded" && fact.name && written && written.toLowerCase() !== fact.name.toLowerCase();
  const detail = factDetail(fact);
  // Orange for the things to check (a recorded allergy, a stopped medicine); green otherwise.
  const alert = (fact.type === "allergy" && (fact.status === "current" || fact.status === "suspected")) || (fact.type === "medicine" && fact.status === "stopped");
  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-3">
      <div>
        <h2 id={headingId} className="text-lg font-medium">
          {factName(fact)}, the source
        </h2>
        <p className="text-sm text-soft">
          Status: {statusLabel(fact)}
          {detail && `. ${detail[0].toUpperCase()}${detail.slice(1)}`}
        </p>
      </div>

      <div className={`rounded-2xl px-4 py-3 text-white ${alert ? "bg-alert" : "bg-rail"}`}>
        <p className="font-medium">
          Latest source: Hospital {fact.hospital}, {formatDate(fact.date)}
        </p>
        <p className="mt-1 break-words">
          <Quote text={fact.quote} file={fact.sources.find((s) => s.quote === fact.quote)?.file} terms={quoteTerms(fact)} />
        </p>
        {renamed && <p className="mt-1 text-sm">Written as {written}.</p>}
      </div>

      {others.map((s) => (
        <div key={`${s.file}-${s.date}`} className="rounded-2xl bg-mint px-4 py-3">
          <p className="font-medium">
            Also Hospital {s.hospital}, {formatDate(s.date)}
          </p>
          <p className="mt-1 break-words">
            <Quote text={s.quote} file={s.file} terms={quoteTerms(fact)} />
          </p>
        </div>
      ))}

      {fact.history.map((h) => (
        <div key={`${h.hospital}-${h.date}`} className="rounded-2xl bg-mint px-4 py-3">
          <p className="font-medium">
            Earlier: Hospital {h.hospital}, {formatDate(h.date)}
          </p>
          <p className="text-sm text-soft">
            {[statusLabel({ type: fact.type, status: h.status }), h.dose, h.frequency && (FREQUENCY_LABELS[h.frequency] ?? h.frequency)]
              .filter(Boolean)
              .join(", ")}
          </p>
          <p className="mt-1 break-words">
            <Quote text={h.quote} terms={quoteTerms(fact, h.dose)} />
          </p>
        </div>
      ))}

      {fact.flags.length > 0 && (
        <ul className="flex flex-wrap gap-2 text-sm">
          {fact.flags.map((flag) => (
            <li key={flag} className="rounded-full bg-peach text-alert-ink px-3 py-0.5 font-medium">
              Warning: {FLAG_LABELS[flag]}
            </li>
          ))}
        </ul>
      )}

      {/* T80: for each warning, the options for checking it. */}
      {factPlans(fact).map((plan) => (
        <CheckOptionsBox key={plan.key} plan={plan} compact idPrefix={`check-${headingId}`} />
      ))}
    </section>
  );
}
