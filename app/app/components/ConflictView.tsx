// Both sides of a disagreement between hospitals, side by side (T75), reached from
// "See both records" on the doctor screen. Neither side is ranked first or hidden
// (CLAUDE.md), and every side shows its hospitals, dates and quotes word for word.
import { statusLabel } from "@/lib/labels";
import { formatDate } from "@/lib/dates";
import { factName } from "@/lib/names";
import type { Fact } from "@/lib/types";
import { factDetail } from "./FactRow";
import Quote, { quoteTerms } from "./Quote";
import { Card } from "./Page";

// A round badge with the hospital's letter. Orange marks the side that records a risk.
export function HospitalDot({ letter, alert = false, size = "h-11 w-11 text-lg" }: { letter: string; alert?: boolean; size?: string }) {
  return (
    <span aria-hidden="true" className={`inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white ${size} ${alert ? "bg-alert" : "bg-rail"}`}>
      {letter}
    </span>
  );
}

// True for the side of a disagreement that records something (an allergy, a medicine),
// as opposed to the side that says "none".
export const recordsRisk = (f: Fact) => f.status !== "none_recorded";

export default function ConflictView({ facts }: { facts: Fact[] }) {
  return (
    <div className="grid gap-5 md:grid-cols-2">
      {facts.map((f) => {
        const detail = factDetail(f);
        return (
          <Card key={f.fact_id} className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2">
              {[...new Set(f.sources.map((s) => s.hospital))].map((h) => (
                <HospitalDot key={h} letter={h} alert={recordsRisk(f)} />
              ))}
              <p className="text-sm text-soft">
                {f.sources.map((s) => `Hospital ${s.hospital}, ${formatDate(s.date)}`).join(". ")}
              </p>
            </div>
            <h2 className="text-3xl font-medium leading-tight break-words">{factName(f)}</h2>
            <p>
              Status: {statusLabel(f)}
              {detail && `. ${detail[0].toUpperCase()}${detail.slice(1)}`}.
            </p>
            <div className="mt-auto flex flex-col gap-2">
              {f.sources.map((s) => (
                <p key={`${s.file}-${s.date}`} className="rounded-2xl bg-mint px-4 py-3 break-words">
                  <Quote text={s.quote} file={s.file} terms={quoteTerms(f)} />
                </p>
              ))}
            </div>
          </Card>
        );
      })}
    </div>
  );
}
