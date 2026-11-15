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
      <h2 id="cost-heading" className="text-lg font-medium">
        AI cost per patient
      </h2>
      <p className="text-sm text-soft">For three hospital records.</p>
      <ul className="mt-2 flex flex-col gap-2">
        {entries.map((e) => (
          <li key={e.model} className="rounded-2xl bg-mint px-4 py-3">
            <p className="text-xl font-medium">{cents(e.us_cents)}</p>
            <p className="text-sm text-soft">{e.model}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
