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

type Measure = "missed" | "false_alarms";
const WORDS: Record<Measure, string> = { missed: "Missed", false_alarms: "False alarms" };

export default function StepChart({ rows }: { rows: ResultRow[] }) {
  const [measure, setMeasure] = useState<Measure>("missed");
  const other: Measure = measure === "missed" ? "false_alarms" : "missed";
  const max = Math.max(1, ...rows.map((r) => r[measure] ?? 0));
  const n = (x: number | null) => (x === null ? "Not run yet" : x.toLocaleString("en-GB"));

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-medium">{WORDS[measure]}, method by method</h2>
        <div role="group" aria-label="What the bars show" className="inline-flex gap-1 rounded-full bg-mint p-1.5">
          {(["missed", "false_alarms"] as Measure[]).map((m) => (
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
      <div className="mt-4 overflow-x-auto">
        <ol className="flex min-w-[36rem] items-end gap-3">
          {rows.map((r) => {
            const value = r[measure];
            const full = r.row === 7;
            const base = r.row === 1;
            return (
              <li key={r.row} className="flex flex-1 flex-col items-center gap-1.5">
                <Tip
                  className="w-full flex-col items-center gap-1.5"
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
                  <span className={`font-medium ${full ? "text-xl text-rail-ink" : ""}`}>{n(value)}</span>
                  <span className="flex h-36 w-full items-end justify-center">
                    <span
                      className={`w-full max-w-12 rounded-t-xl rounded-b ${full ? "bg-rail" : base ? "bg-alert" : "bg-leaf"}`}
                      style={{ height: `${value === null ? 0 : Math.max(3, (value / max) * 100)}%` }}
                    />
                  </span>
                </Tip>
                <span className={`h-12 text-center text-xs leading-tight ${full ? "font-medium text-rail-ink" : "text-soft"}`}>
                  {SHORT[r.row] ?? r.method}
                </span>
              </li>
            );
          })}
        </ol>
      </div>
      <p className="mt-1 text-sm text-soft">Orange is the keyword baseline. Dark green is the full tool. Shorter is better.</p>
    </>
  );
}
