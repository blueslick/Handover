"use client";
// The bar chart on the "How we tested" tab (T75): one bar per method, so the drop from
// the keyword baseline to the full tool can be seen at a glance. A switch changes the
// bars between missed facts and false alarms. Every bar has its number written above it,
// and the full table is one tap away, so nothing depends on reading bar heights.
import { useState } from "react";
import type { ResultRow } from "@/lib/results";
import Tip from "../components/Tip";

// Short names for under the bars; the full method name shows on hover and in the table.
const SHORT: Record<number, string> = {
  1: "Keyword search",
  2: "medSpaCy",
  3: "Keyword, with rules",
  4: "Claude, plain lists",
  5: "With status labels",
  6: "With Check",
  7: "Full tool",
  8: "Cheaper model",
};

// T78: a third button, "Disagreements shown", so removing the full table loses nothing big.
type Measure = "missed" | "false_alarms" | "conflicts_shown";
const WORDS: Record<Measure, string> = { missed: "Missed", false_alarms: "False alarms", conflicts_shown: "Disagreements shown" };
const MEANING: Record<Measure, string> = {
  missed: "Missed: a fact in the answer key that the method did not find. Shorter is better.",
  false_alarms: "False alarms: a fact the method reported that is not in the answer key. Shorter is better.",
  conflicts_shown: "Disagreements shown: places where the hospitals disagree that the method showed side by side. Taller is better.",
};

export default function StepChart({ rows }: { rows: ResultRow[] }) {
  const [measure, setMeasure] = useState<Measure>("missed");
  const other: Measure = measure === "missed" ? "false_alarms" : "missed";
  // Disagreements are drawn out of the total in the answer keys (38), so a full bar means all of them.
  const max = measure === "conflicts_shown" ? Math.max(1, ...rows.map((r) => r.conflicts_total ?? r.conflicts_shown ?? 0)) : Math.max(1, ...rows.map((r) => r[measure] ?? 0));
  const n = (x: number | null) => (x === null ? "Not run yet" : x.toLocaleString("en-GB"));

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-medium">{WORDS[measure]}, method by method</h2>
        <div role="group" aria-label="What the bars show" className="inline-flex gap-1 rounded-full bg-mint p-1.5">
          {(["missed", "false_alarms", "conflicts_shown"] as Measure[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMeasure(m)}
              aria-pressed={measure === m}
              className={`rounded-full px-4 py-1.5 ${measure === m ? "bg-rail text-white font-medium" : "hover:bg-leaf"}`}
            >
              {WORDS[m]}
            </button>
          ))}
        </div>
      </div>
      {/* Top padding leaves room for the hover extras, which open above the bars. */}
      <div className="mt-2 overflow-x-auto pt-14">
        <ol className="flex min-w-[36rem] items-end gap-3">
          {rows.map((r) => {
            const value = r[measure];
            // Same colours as the table: baselines (rows 1 to 3) orange, the full tool (rows 7 and 8) dark green.
            const full = r.row === 7 || r.row === 8;
            const base = r.row >= 1 && r.row <= 3;
            const main = r.row === 7;
            return (
              <li key={r.row} className="flex flex-1 flex-col items-center gap-1.5">
                <Tip
                  className="w-full flex-col items-center gap-1.5"
                  up
                  tip={
                    <>
                      <span className="block font-medium">
                        Row {r.row}: {r.method}
                      </span>
                      <span className="block">
                        {WORDS[other]}: {n(r[other])}
                      </span>
                    </>
                  }
                >
                  <span className={`font-medium ${main ? "text-xl text-rail-ink" : ""}`}>
                    {measure === "conflicts_shown" && value !== null && r.conflicts_total != null ? `${n(value)} of ${n(r.conflicts_total)}` : n(value)}
                  </span>
                  <span className="flex h-36 w-full items-end justify-center">
                    <span
                      className={`w-full max-w-12 rounded-t-xl rounded-b ${full ? "bg-rail" : base ? "bg-alert" : "bg-leaf"}`}
                      style={{ height: `${value === null || (value === 0 && measure === "conflicts_shown") ? 0 : Math.max(3, (value / max) * 100)}%` }}
                    />
                  </span>
                </Tip>
                <span className={`h-12 text-center text-xs leading-tight ${main ? "font-medium text-rail-ink" : "text-soft"}`}>
                  {SHORT[r.row] ?? r.method}
                </span>
              </li>
            );
          })}
        </ol>
      </div>
      <p className="mt-1 text-sm text-soft">{MEANING[measure]}</p>
      <p className="mt-1 text-sm text-soft">
        Orange bars are the baselines (no AI). Dark green is the full tool. Each bar from left to right adds one
        step; the last bar is the full tool again on a cheaper model.
      </p>
    </>
  );
}
