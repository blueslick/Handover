// The AI cost in the "How we tested" tab's Details fold (T39, new look T75).
// T90: a table, Claude Sonnet 5.5 against Claude Haiku 5.5, per patient and per 1,000
// patients, with each model's missed facts and false alarms beside it so the trade-off is
// plain. Every number comes from app/data/results.json (built from cost_per_patient.csv and
// buildup_table.csv by scripts/make-results.mjs); none is typed here.
// An older file without the per-1,000 numbers falls back to the old one-line list.
import type { CostEntry, ResultRow } from "@/lib/results";
import { fmt } from "./Bars";

// 3.3 -> "3.3 US cents"; null -> "Not run yet".
function cents(n: number | null): string {
  return n === null ? "Not run yet" : `${n} US cents`;
}

// 42.66 -> "US$42.66"; 0.1 -> "US$0.10".
function dollars(n: number): string {
  return `US$${n.toFixed(2)}`;
}

export default function CostLine({ entries, rows }: { entries?: CostEntry[]; rows?: ResultRow[] }) {
  if (!entries || entries.length === 0) return null;
  const table = entries.every((e) => e.us_cents !== null && typeof e.usd_per_1000 === "number");
  const result = (e: CostEntry) => rows?.find((r) => r.row === e.row);
  const patients = entries[0].patients;

  if (!table) {
    return (
      <section aria-labelledby="cost-heading">
        <h2 id="cost-heading" className="font-semibold">
          AI cost per patient
        </h2>
        <ul className="mt-1 flex list-disc flex-col gap-1 pl-5">
          {entries.map((e) => (
            <li key={e.model}>
              <span className="font-medium">{cents(e.us_cents)}</span> for three hospital records: {e.model}
            </li>
          ))}
        </ul>
      </section>
    );
  }

  return (
    <section aria-labelledby="cost-heading">
      <h2 id="cost-heading" className="font-semibold">
        AI cost: Claude Sonnet 5.5 against Claude Haiku 5.5
      </h2>
      {/* On a narrow screen the table scrolls inside its own box, not the page. */}
      <div className="mt-1 overflow-x-auto rounded-box border border-line">
        <table className="dt">
          <thead>
            <tr>
              <th scope="col">Model</th>
              <th scope="col" className="num">Per patient</th>
              <th scope="col" className="num">Per 1,000 patients</th>
              <th scope="col" className="num">Missed</th>
              <th scope="col" className="num">False alarms</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => {
              const r = result(e);
              const main = e.row === 7;
              return (
                <tr key={e.model}>
                  <td className={main ? "whitespace-nowrap font-semibold" : "whitespace-nowrap"}>
                    {e.short ?? e.model}
                    {main && <span className="block text-xs font-normal text-quiet">The model the tool uses</span>}
                  </td>
                  <td className="num whitespace-nowrap">{cents(e.us_cents)}</td>
                  <td className="num">{dollars(e.usd_per_1000!)}</td>
                  <td className="num whitespace-nowrap">{r?.missed ?? "–"}{r?.key_facts ? ` of ${fmt(r.key_facts)}` : ""}</td>
                  <td className="num">{r?.false_alarms ?? "–"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-1 text-xs text-quiet">
        One patient is three hospital records (three calls to the AI). Worked out from the real held-out run
        {typeof patients === "number" && ` on ${patients} patients`}, retries included. Prices used, per million word pieces
        (tokens) in and out:{" "}
        {entries
          .filter((e) => typeof e.usd_per_million_in === "number" && typeof e.usd_per_million_out === "number")
          .map((e) => `${e.short ?? e.model} ${dollars(e.usd_per_million_in!)} and ${dollars(e.usd_per_million_out!)}`)
          .join("; ")}
        .
      </p>
    </section>
  );
}
