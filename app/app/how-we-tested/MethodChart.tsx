"use client";
// The headline chart (T81, T82): missed facts and false alarms for the full tool and the
// other methods, with a switch between two views of the same test:
//   All facts                       every fact in the answer key (from buildup_table.csv);
//   Allergies and medicines only    the facts the baselines actually look for, which is
//                                   also the only set Microsoft Azure was scored on
//                                   (from azure_line.csv).
// Both panels of a view share one scale. Every number comes from app/data/results.json.
import { useState } from "react";
import { Axis, BarRow, fmt, niceMax, percent } from "./Bars";

export interface MethodLine {
  label: string;
  tool: boolean;
  missed: number;
  false_alarms: number;
  matched: number;
  key_facts: number;
  output_facts: number;
}

export interface MethodView {
  key: string;
  button: string;
  // What "the others" are called in the title: "baseline" or "of the others".
  others: string;
  lines: MethodLine[];
  // A short note opened by a tap, for the Azure caveats.
  details?: { summary: string; text: string; link?: { href: string; label: string } };
}

export default function MethodChart({ views }: { views: MethodView[] }) {
  const [chosen, setChosen] = useState(views[0]?.key ?? "");
  const view = views.find((v) => v.key === chosen) ?? views[0];
  if (!view) return null;
  const tool = view.lines.find((l) => l.tool);
  const rest = view.lines.filter((l) => !l.tool);
  const max = niceMax(view.lines.flatMap((l) => [l.missed, l.false_alarms]));
  const bar = (tool: boolean) => (tool ? "bg-accent" : "bg-bar");
  return (
    <div className="flex flex-col gap-3">
      {views.length > 1 && (
        <div role="group" aria-label="Which facts to count" className="flex flex-wrap gap-2">
          {views.map((v) => (
            <button
              key={v.key}
              type="button"
              aria-pressed={v.key === view.key}
              onClick={() => setChosen(v.key)}
              className={`h-8 rounded-ctl border px-3 font-medium ${v.key === view.key ? "border-accent bg-accent text-white" : "border-line-strong bg-surface text-ink"}`}
            >
              {v.button}
            </button>
          ))}
        </div>
      )}
      {tool && rest.length > 0 && (
        <h2 className="text-base font-semibold">
          Full tool: {fmt(tool.missed)} missed, {fmt(tool.false_alarms)} false alarms. Best {view.others} on each: {fmt(Math.min(...rest.map((l) => l.missed)))} missed,{" "}
          {fmt(Math.min(...rest.map((l) => l.false_alarms)))} false alarms.
        </h2>
      )}
      <div className="grid gap-x-8 gap-y-4 lg:grid-cols-2">
        <div>
          <h3 className="mb-1 font-semibold">Missed facts (fewer is better)</h3>
          {view.lines.map((l) => (
            <BarRow key={l.label} label={l.label} strong={l.tool} parts={[{ n: l.missed, className: bar(l.tool) }]} max={max} value={fmt(l.missed)} note={`${percent(l.matched, l.key_facts)} found`} labelWidth="sm:w-56" />
          ))}
          <Axis max={max} labelWidth="sm:w-56" />
        </div>
        <div>
          <h3 className="mb-1 font-semibold">False alarms (fewer is better)</h3>
          {view.lines.map((l) => (
            <BarRow key={l.label} label={l.label} strong={l.tool} parts={[{ n: l.false_alarms, className: bar(l.tool) }]} max={max} value={fmt(l.false_alarms)} note={`${percent(l.matched, l.output_facts)} correct`} labelWidth="sm:w-56" />
          ))}
          <Axis max={max} labelWidth="sm:w-56" />
        </div>
      </div>
      {view.details && (
        <details className="border-t border-line pt-2">
          <summary className="font-semibold">{view.details.summary}</summary>
          <p className="mt-1">
            {view.details.text}{" "}
            {view.details.link && (
              <a href={view.details.link.href} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">
                {view.details.link.label}
                <span className="sr-only"> (opens in a new tab)</span>
              </a>
            )}
          </p>
        </details>
      )}
    </div>
  );
}
