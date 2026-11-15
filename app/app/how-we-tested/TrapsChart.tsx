// The planted traps chart on the "How we tested" tab (T78). For each kind of trap we planted
// in the hospital records, two bars: how many the full tool (row 7) caught and how many the
// keyword baseline (row 1) caught, out of the traps that could be scored. Numbers come from
// data/results.json (filled from traps_by_type.csv), never typed. Each bar has "x of y"
// written next to it.
import type { TrapRow } from "@/lib/results";

export default function TrapsChart({ traps }: { traps?: TrapRow[] }) {
  if (!traps || traps.length === 0) return <p>Not run yet.</p>;
  const width = (n: number, of: number) => `${of > 0 && n > 0 ? Math.max(1.5, (n / of) * 100) : 0}%`;
  const total = traps.reduce((a, t) => a + t.scored, 0);

  return (
    <>
      <h2 className="text-lg font-medium">Planted traps caught</h2>
      <p className="mt-1 text-sm text-soft">
        We planted {total.toLocaleString("en-GB")} traps in the held-out records on purpose, the kind of slip that
        happens when records move between hospitals. Longer is better.
      </p>
      <ul className="mt-3 flex flex-col gap-4">
        {traps.map((t) => (
          <li key={t.kind}>
            <p className="text-sm font-medium">{t.label}</p>
            <div className="mt-1 flex flex-col gap-1">
              {[
                { who: "Full tool", n: t.tool_caught, bar: "bg-rail", text: "font-medium text-rail-ink" },
                { who: "Keyword search", n: t.baseline_caught, bar: "bg-alert", text: "" },
              ].map((b) => (
                <div key={b.who} className="flex items-center gap-2">
                  <span className="sr-only">{b.who}:</span>
                  <span className="h-4 flex-1 rounded-full bg-mint">
                    <span className={`block h-4 rounded-full ${b.bar}`} style={{ width: width(b.n, t.scored) }} />
                  </span>
                  <span className={`w-36 shrink-0 text-sm ${b.text}`}>
                    {b.n} of {t.scored} <span className="text-xs text-soft">{b.who === "Full tool" ? "tool" : "keyword"}</span>
                  </span>
                </div>
              ))}
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-sm text-soft">
        Dark green is the full tool. Orange is keyword search (no AI). The last two kinds are easy for both, so
        only the first two tell the methods apart.
      </p>
    </>
  );
}
