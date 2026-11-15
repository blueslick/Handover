// Where one fact came from (T75, restyled in T81), shown in the right-hand panel when its
// row is chosen: every hospital's quote word for word, the earlier values, and any warning.
// This is the "fact card": the fact, its status, the hospital and date, any warning, and
// the exact source quote, all one tap from the row.
import { factPlans } from "@/lib/checkOptions";
import { FLAG_LABELS, FREQUENCY_LABELS, statusLabel } from "@/lib/labels";
import { formatDate } from "@/lib/dates";
import { hospitalFull } from "@/lib/hospitals";
import { capitalise, factName } from "@/lib/names";
import type { Fact } from "@/lib/types";
import CheckOptionsBox from "./CheckOptionsBox";
import { factDetail } from "./FactRow";
import { QuoteBlock, quoteTerms } from "./Quote";
import Tag from "./Tag";

// "1000 mg" is often written "1 g" in the records. Returns "1 g" when a quote says it that way.
function writtenInGrams(fact: Fact): string | null {
  const mg = /^(\d+(?:\.\d+)?) mg$/.exec(fact.dose ?? "");
  if (!mg || Number(mg[1]) < 1000 || Number(mg[1]) % 1000 !== 0) return null;
  const grams = `${Number(mg[1]) / 1000} g`;
  const re = new RegExp(`(?<![A-Za-z0-9.])${grams}(?![A-Za-z0-9])`, "i");
  return fact.sources.some((s) => re.test(s.quote)) ? grams : null;
}

// headingId lets the panel appear twice on a page (in the right-hand panel on a laptop,
// under the chosen row on a phone) without two parts sharing one id.
export default function SourcePanel({ fact, headingId = "source-heading" }: { fact: Fact; headingId?: string }) {
  // The latest source first, then every other hospital that says the same.
  const latest = fact.sources.find((s) => s.hospital === fact.hospital && s.date === fact.date && s.quote === fact.quote);
  const others = fact.sources.filter((s) => s !== latest);
  const written = fact.name_as_written ?? "";
  const renamed = fact.status !== "none_recorded" && fact.name && written && written.toLowerCase() !== fact.name.toLowerCase();
  const grams = writtenInGrams(fact);
  const detail = factDetail(fact);
  const unverified = fact.flags.includes("unverified");
  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-3">
      <div>
        <h2 id={headingId} className="text-base font-semibold">
          Source: {factName(fact)}
        </h2>
        <p className="text-quiet">
          {statusLabel(fact)}
          {detail && `, ${detail}`}
        </p>
      </div>

      {/* One line for all quotes. A quote is marked only when it was NOT found word for word. */}
      {unverified ? <p><Tag kind="warn">{FLAG_LABELS.unverified}</Tag></p> : <p className="text-quiet">Quotes are word for word from the records.</p>}

      {(renamed || grams) && (
        <p>
          {renamed && `${capitalise(written)} is a brand of ${fact.name}. `}
          {grams && `${grams} is shown as ${fact.dose}.`}
        </p>
      )}

      {/* When the latest quote is not among the sources, it is still shown first. */}
      {!latest && (
        <div className="flex flex-col gap-1">
          <p>
            {hospitalFull(fact.hospital)}, {formatDate(fact.date)}
          </p>
          <QuoteBlock text={fact.quote} terms={quoteTerms(fact)} />
        </div>
      )}
      {[...(latest ? [latest] : []), ...others].map((s) => (
        <div key={`${s.file}-${s.date}`} className="flex flex-col gap-1">
          <p>
            {hospitalFull(s.hospital)}, {formatDate(s.date)}
          </p>
          <QuoteBlock text={s.quote} file={s.file} terms={quoteTerms(fact)} />
        </div>
      ))}

      {fact.history.map((h) => {
        const was = [statusLabel({ type: fact.type, status: h.status }), h.dose, h.frequency && (FREQUENCY_LABELS[h.frequency] ?? h.frequency)].filter(Boolean).join(", ");
        const doseDiffers = Boolean(h.dose) && h.dose !== fact.dose;
        return (
          <div key={`${h.hospital}-${h.date}`} className="flex flex-col gap-1">
            <p>
              {hospitalFull(h.hospital)}, {formatDate(h.date)}{" "}
              <span className="text-quiet">
                {doseDiffers ? "Earlier dose" : "Earlier record"}: {was.toLowerCase()}
              </span>
            </p>
            <QuoteBlock text={h.quote} terms={quoteTerms(fact, h.dose)} />
          </div>
        );
      })}

      {/* T80: for each warning, the options for checking it, folded until tapped. */}
      {factPlans(fact).map((plan) => (
        <CheckOptionsBox key={plan.key} plan={plan} compact idPrefix={`check-${headingId}`} />
      ))}
    </section>
  );
}
