// The cost per patient in the right-hand panel of the "How we tested" tab (T39, new look T75).
// Shows "Not run yet" for any model whose cost is not in app/data/results.json yet.
import type { CostEntry } from "@/lib/results";

// 3.3 -> "3.3 US cents"; null -> "Not run yet".
function cents(n: number | null): string {
  return n === null ? "Not run yet" : `${n} US cents`;
}

export default function CostLine({ entries }: { entries?: CostEntry[] }) {
  if (!entries || entries.length === 0) return null;
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
