"use client";
// The age and sex chart on the "How we tested" tab (T78, replaces the T71 table at Daniel's
// request). One row per group, with two bars: the full tool (row 7) and the keyword baseline
// (row 1). A switch changes the bars between facts found and false alarms. Every bar has its
// number written next to it, so nothing depends on reading bar lengths.
import { useState } from "react";
import type { AgeSexRow } from "@/lib/results";

type Measure = "found" | "false_alarms";
const WORDS: Record<Measure, string> = { found: "Facts found", false_alarms: "False alarms" };

const pct = (part: number, whole: number) => (whole > 0 ? (part / whole) * 100 : 0);

export default function AgeSexChart({ groups }: { groups?: AgeSexRow[] }) {
  const [measure, setMeasure] = useState<Measure>("found");
  if (!groups || groups.length === 0) return <p>Not run yet.</p>;

  // Every number the chart needs, worked out from the results file.
  const lines = groups.map((g) => {
    const facts = g.key_facts ?? 0;
    const found = (missed: number | null) => (missed === null ? null : pct(facts - missed, facts));
    return {
      key: `${g.age_band}-${g.sex}`,
      label: `${g.age_band}, ${g.sex === "F" ? "female" : g.sex === "M" ? "male" : g.sex}`,
      patients: g.patients,
      tool: measure === "found" ? found(g.tool_missed) : g.tool_false_alarms,
      base: measure === "found" ? found(g.baseline_missed) : g.baseline_false_alarms,
      toolFound: found(g.tool_missed),
    };
  });
  // The weakest group: where the full tool found the smallest share of facts.
  const weakest = lines.reduce((a, b) => ((b.toolFound ?? 101) < (a.toolFound ?? 101) ? b : a));
  const max = measure === "found" ? 100 : Math.max(1, ...lines.map((l) => Math.max(l.tool ?? 0, l.base ?? 0)));
  const say = (v: number | null) =>
    v === null ? "Not run yet" : measure === "found" ? `${v.toFixed(1)}%` : v.toLocaleString("en-GB");
  const width = (v: number | null) => `${v === null || v === 0 ? 0 : Math.max(1.5, (v / max) * 100)}%`;

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-medium">{WORDS[measure]}, by age and sex</h2>
        <div role="group" aria-label="What the bars show" className="inline-flex gap-1 rounded-full bg-mint p-1.5">
          {(["found", "false_alarms"] as Measure[]).map((m) => (
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
      <p className="mt-1 text-sm text-soft">
        Every held-out patient is in one of eight groups of 20: four age bands, each split by sex.{" "}
        {measure === "found" ? "Longer is better." : "Shorter is better."}
      </p>
      <ul className="mt-3 flex flex-col gap-3">
        {lines.map((l) => (
          <li key={l.key} className="grid gap-x-4 gap-y-1 sm:grid-cols-[10rem_1fr] sm:items-center">
            <p className="text-sm">
              <span className="font-medium">{l.label}</span>
              {l === weakest && (
                <span className="ml-2 inline-block whitespace-nowrap rounded-full bg-alert px-2.5 py-0.5 text-xs font-medium text-white">
                  Weakest group
                </span>
              )}
            </p>
            <div className="flex flex-col gap-1">
              {[
                { who: "Full tool", v: l.tool, bar: "bg-rail", text: "font-medium text-rail-ink" },
                { who: "Keyword search", v: l.base, bar: "bg-alert", text: "" },
              ].map((b) => (
                <div key={b.who} className="flex items-center gap-2">
                  <span className="sr-only">{b.who}:</span>
                  <span className="h-4 flex-1 rounded-full bg-mint">
                    <span className={`block h-4 rounded-full ${b.bar}`} style={{ width: width(b.v) }} />
                  </span>
                  <span className={`w-28 shrink-0 text-sm ${b.text}`}>
                    {say(b.v)} <span className="text-xs text-soft">{b.who === "Full tool" ? "tool" : "keyword"}</span>
                  </span>
                </div>
              ))}
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-sm text-soft">Dark green is the full tool. Orange is keyword search (no AI).</p>
    </>
  );
}
