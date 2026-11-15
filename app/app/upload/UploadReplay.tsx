"use client";
// The moving part of the upload screen (T28, upgraded in T63). Press one button and all
// three hospital records go through their steps at the same time (Read, Extract, Check),
// then one Merge step joins them into the patient's record.
// It replays a saved run: every number shown comes from the saved files. The pauses are
// only there so each step can be seen; the Extract pause is longer for records whose saved
// reply was longer, so the three rows don't move in lockstep.
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { Walkthrough, WalkthroughHospital } from "@/lib/walkthrough";
import FactList from "../components/FactList";

// The merged record's counts, from app/data/index.json, only when it is the same run.
export interface MergedSummary {
  facts: number;
  conflicts: number;
}

type StepState = "waiting" | "running" | "finished";

// How long each step stays on screen in the replay, in milliseconds.
const READ_MS = 900;
const CHECK_MS = 1300;
const MERGE_MS = 1800;
function extractMs(h: WalkthroughHospital) {
  const out = h.tokens?.output_tokens ?? 400;
  return 1200 + Math.min(out, 1000) * 4;
}

const HOSPITAL_STEPS = [
  { key: "read", label: "Read the file" },
  { key: "extract", label: "Extract the facts with Claude" },
  { key: "check", label: "Check every fact against the record's own words" },
] as const;

// Start and end times (ms after pressing Start) of each hospital's three steps.
function scheduleFor(h: WalkthroughHospital) {
  const lengths = [READ_MS, extractMs(h), CHECK_MS];
  let t = 0;
  return lengths.map((len) => {
    const step = { start: t, end: t + len };
    t += len;
    return step;
  });
}

function stateAt(elapsed: number | null, start: number, end: number): StepState {
  if (elapsed === null || elapsed < start) return "waiting";
  return elapsed < end ? "running" : "finished";
}

// One step, said in words (never colour alone): waiting, running now, or finished.
function StepLine({ label, state }: { label: string; state: StepState }) {
  return (
    <li className="flex items-start gap-2">
      {state === "running" ? (
        <span
          aria-hidden="true"
          className="mt-1 inline-block h-4 w-4 shrink-0 rounded-full border-2 border-zinc-800 border-t-transparent motion-safe:animate-spin"
        />
      ) : (
        <span aria-hidden="true" className="inline-block w-4 shrink-0 text-center font-bold">
          {state === "finished" ? "✓" : "·"}
        </span>
      )}
      <span className={state === "running" ? "font-semibold" : state === "waiting" ? "text-zinc-600" : ""}>
        {label}
        <span className="text-sm">
          {state === "running" ? " (running now)" : state === "finished" ? " (done)" : " (waiting)"}
        </span>
      </span>
    </li>
  );
}

function HospitalRow({ h, elapsed }: { h: WalkthroughHospital; elapsed: number | null }) {
  const schedule = scheduleFor(h);
  const done = elapsed !== null && elapsed >= schedule[2].end;
  return (
    <section aria-label={`Hospital ${h.hospital}`} className="border-2 border-zinc-800 rounded p-3 flex flex-col">
      <h2 className="text-lg font-semibold">Hospital {h.hospital}</h2>
      <p className="text-sm">{h.format}</p>
      <p className="text-xs text-zinc-700">File: {h.file}</p>

      {h.state === "not_run" ? (
        <p role="status" className="mt-3 border border-zinc-700 rounded p-2 text-sm">
          This record has not been run through the tool yet, so there is nothing to replay.
        </p>
      ) : (
        <ol className="mt-3 flex flex-col gap-1 text-sm">
          {HOSPITAL_STEPS.map((s, i) => (
            <StepLine key={s.key} label={s.label} state={stateAt(elapsed, schedule[i].start, schedule[i].end)} />
          ))}
        </ol>
      )}

      {done && (
        <p className="mt-2 text-sm font-medium">
          {h.facts.length} facts read, each with its quote
          {h.retried ? " (the Check step asked for one retry)" : ""}.
        </p>
      )}

      <details className="mt-3 text-sm">
        <summary className="cursor-pointer underline">Show the record</summary>
        <pre className="mt-2 max-h-60 overflow-auto border border-zinc-400 rounded bg-zinc-50 p-2 text-xs whitespace-pre-wrap break-words">
          {h.record_text}
        </pre>
      </details>
      {done && (
        <details className="mt-2 text-sm">
          <summary className="cursor-pointer underline">Show what the tool read</summary>
          <div className="mt-2">
            <FactList facts={h.facts} />
          </div>
        </details>
      )}
    </section>
  );
}

export default function UploadReplay({
  walkthrough,
  merged,
}: {
  walkthrough: Walkthrough;
  merged: MergedSummary | null;
}) {
  const hospitals = walkthrough.hospitals;
  const ready = hospitals.filter((h) => h.state === "ready");
  const canMerge = ready.length === hospitals.length && ready.length > 0;

  // When Start was pressed (ms), and how long ago that was. null = not started.
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState<number | null>(null);

  const lastRecordEnd = Math.max(0, ...ready.map((h) => scheduleFor(h)[2].end));
  const mergeStart = lastRecordEnd;
  const mergeEnd = mergeStart + MERGE_MS;
  const finished = elapsed !== null && elapsed >= (canMerge ? mergeEnd : lastRecordEnd);

  // A clock that ticks while the replay plays, and stops once everything is done.
  useEffect(() => {
    if (startedAt === null || finished) return;
    const timer = setInterval(() => setElapsed(Date.now() - startedAt), 150);
    return () => clearInterval(timer);
  }, [startedAt, finished]);

  // T68 item 26: when the replay ends, bring the "record is ready" box into view and put
  // the keyboard on its button, so the next step is obvious (and on camera).
  const readyRef = useRef<HTMLDivElement>(null);
  const openRef = useRef<HTMLAnchorElement>(null);
  useEffect(() => {
    if (!finished || !canMerge) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    readyRef.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" });
    openRef.current?.focus({ preventScroll: true });
  }, [finished, canMerge]);

  const start = () => {
    const now = Date.now();
    setStartedAt(now);
    setElapsed(0);
  };

  const recordsDone = elapsed !== null && elapsed >= lastRecordEnd;
  const mergeState: StepState = canMerge ? stateAt(elapsed, mergeStart, mergeEnd) : "waiting";
  const mergeLabel = !canMerge
    ? "Merge the records with the six rules: needs all three records to be run first"
    : mergeState === "waiting"
      ? "Merge the three readings into one record with the six rules (waits for all three records)"
      : "Merge the three readings into one record with the six rules";

  // One short line for screen readers, so they hear progress without every step.
  const spoken =
    elapsed === null
      ? ""
      : finished && canMerge
        ? "The record is ready."
        : recordsDone
          ? "All three records checked. Merging."
          : "Reading all three records.";

  return (
    <div className="mt-6">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={start}
          disabled={elapsed !== null && !finished}
          className="border border-zinc-800 bg-zinc-800 text-white rounded px-4 py-2 disabled:opacity-60"
        >
          {/* T68 item 25: the button says it is a replay. */}
          {elapsed === null ? "Replay: read all three records" : finished ? "Replay again" : "Playing…"}
        </button>
        <p aria-live="polite" className="text-sm font-medium">
          {spoken}
        </p>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-3">
        {hospitals.map((h) => (
          <HospitalRow key={h.hospital} h={h} elapsed={elapsed} />
        ))}
      </div>

      <section aria-label="Merge step" className="mt-4 border-2 border-zinc-800 rounded p-3">
        <h2 className="text-lg font-semibold">Merge</h2>
        <ol className="mt-2 text-sm">
          <StepLine label={mergeLabel} state={mergeState} />
        </ol>
      </section>

      {finished && canMerge && (
        <div ref={readyRef} role="status" className="mt-4 border-4 border-zinc-800 bg-zinc-50 rounded p-5">
          <p className="text-lg font-semibold">
            {merged
              ? `The record is ready: ${merged.facts} facts and ${merged.conflicts} ${
                  merged.conflicts === 1 ? "conflict" : "conflicts"
                } for the doctor to see.`
              : "The record is ready."}
          </p>
          <Link
            ref={openRef}
            href={`/?id=${walkthrough.patient_id}`}
            className="mt-3 inline-block border-2 border-zinc-900 bg-zinc-900 text-white text-lg font-semibold rounded px-6 py-3 hover:bg-zinc-700"
          >
            Open the doctor screen for {walkthrough.patient_id} →
          </Link>
        </div>
      )}
    </div>
  );
}
