// The cost-per-patient line under the results table on the "How we tested" tab (T39).
// Shows "Not run yet" for any model whose cost is not in app/data/results.json yet.
import type { CostEntry } from "@/lib/results";

// 3.3 -> "3.3 US cents"; null -> "Not run yet".
function cents(n: number | null): string {
  return n === null ? "Not run yet" : `${n} US cents`;
}

export default function CostLine({ entries }: { entries?: CostEntry[] }) {
  if (!entries || entries.length === 0) return null;
  return (
    <div className="mt-2 text-sm">
      <p className="font-medium">AI cost per patient (three hospital records):</p>
      <ul className="list-disc pl-5">
        {entries.map((e) => (
          <li key={e.model}>
            {e.model}: {cents(e.us_cents)}
          </li>
        ))}
      </ul>
    </div>
  );
}
