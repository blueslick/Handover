// T67 (from Q09): greyed history box for an older "No regular medicines recorded" line,
// shown under the medicine lists when a later record lists current medicines.
// It says "Older record" in words and shows the hospital, date and quote, so nothing
// is hidden and nothing relies on colour alone.
import { statusLabel } from "@/lib/labels";
import type { Fact } from "@/lib/types";
import { formatDate } from "@/lib/dates";

export default function OlderRecordNote({ facts }: { facts: Fact[] }) {
  if (facts.length === 0) return null;
  return (
    <section
      aria-label="Older record: medicines"
      className="rounded-3xl border border-dashed border-soft text-soft p-5"
    >
      <h2 className="text-base font-medium">Older record</h2>
      <p className="mt-1 text-sm">
        A later hospital record lists current medicines, so this earlier line is kept here as
        history only.
      </p>
      <ul className="mt-2 list-disc pl-5 text-sm">
        {facts.flatMap((fact) =>
          fact.sources.map((s) => (
            <li key={`${fact.fact_id}-${s.file}-${s.date}`} className="break-words">
              {statusLabel(fact)} (Hospital {s.hospital}, {formatDate(s.date)}): “{s.quote}”
            </li>
          )),
        )}
      </ul>
    </section>
  );
}
