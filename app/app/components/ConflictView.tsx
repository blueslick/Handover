// Both sides of a disagreement between hospitals, side by side (T75, restyled in T81),
// reached from "See both" on the doctor screen. Neither side is ranked first or hidden
// (CLAUDE.md), and every side shows its hospitals, dates and quotes word for word.
import { statusLabel } from "@/lib/labels";
import { formatDate } from "@/lib/dates";
import { hospitalFull } from "@/lib/hospitals";
import { factName } from "@/lib/names";
import type { Fact } from "@/lib/types";
import { factDetail } from "./FactRow";
import { QuoteBlock, quoteTerms } from "./Quote";
import { Card } from "./Page";

export default function ConflictView({ facts }: { facts: Fact[] }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {facts.map((f) => {
        const detail = factDetail(f);
        return (
          <Card key={f.fact_id} className="flex flex-col gap-2">
            <h2 className="text-lg font-semibold break-words">{factName(f)}</h2>
            <p>
              {statusLabel(f)}
              {detail && `, ${detail}`}
            </p>
            {f.sources.map((s) => (
              <div key={`${s.file}-${s.date}`} className="flex flex-col gap-1">
                <p>
                  {hospitalFull(s.hospital)}, {formatDate(s.date)}
                </p>
                <QuoteBlock text={s.quote} file={s.file} terms={quoteTerms(f)} />
              </div>
            ))}
          </Card>
        );
      })}
    </div>
  );
}
