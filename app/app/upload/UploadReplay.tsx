"use client";
// The moving part of the hospital records screen (T28, T63; new look in T75). Press one
// button and all three hospital records go through their steps at the same time (Read,
// Extract, Check), then one Merge step joins them into the patient's record.
// It replays a saved run: every number shown comes from the saved files. The pauses are
// only there so each step can be seen; the Extract pause is longer for records whose saved
// reply was longer, so the three records don't move in lockstep.
// T75: the main column shows the steps, one small card per hospital and the merge. The
// chosen hospital's record and what the tool read from it show in the right-hand panel.
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { Walkthrough, WalkthroughHospital } from "@/lib/walkthrough";
import { statusLabel } from "@/lib/labels";
import { factName } from "@/lib/names";
import FactList from "../components/FactList";
import { factDetail } from "../components/FactRow";
import Page, { Card } from "../components/Page";
import Tip from "../components/Tip";
import RecordText from "./RecordText";

// The merged record's counts, from app/data/index.json, only when it is the same run.
export interface MergedSummary {
  facts: number;
  conflicts: number;
}

// One thing the Merge step did for this patient (worked out on the server, in page.tsx).
export interface MergeNote {
  title: string;
  text: string;
}

type StepState = "waiting" | "running" | "finished";
const STATE_WORD: Record<StepState, string> = { waiting: "waiting", running: "running now", finished: "done" };

// How long each step stays on screen in the replay, in milliseconds.
const READ_MS = 900;
const CHECK_MS = 1300;
const MERGE_MS = 1800;
function extractMs(h: WalkthroughHospital) {
  const out = h.tokens?.output_tokens ?? 400;
  return 1200 + Math.min(out, 1000) * 4;
}

// The four steps: a short name for the pill, the words used while it runs, and the
// one-line explanation (shown on hover and in "The four steps").
const STEPS = [
  { key: "read", label: "Read", doing: "Reading the file", what: "Open each hospital's file." },
  { key: "extract", label: "Extract (AI)", doing: "Extracting the facts with Claude", what: "Claude lists every fact with the exact words it came from." },
  { key: "check", label: "Check", doing: "Checking every fact against the record's own words", what: "Code checks each fact against the record's own words. No AI." },
  { key: "merge", label: "Merge", doing: "Merging", what: "Six written rules join the three lists into one record. No AI." },
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

// The small mark in front of a step: a tick when done, a spinner while running, a dot while waiting.
function Mark({ state }: { state: StepState }) {
  if (state === "running") {
    return <span aria-hidden="true" className="inline-block h-5 w-5 shrink-0 rounded-full border-2 border-rail border-t-transparent motion-safe:animate-spin" />;
  }
  return (
    <span aria-hidden="true" className={`inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${state === "finished" ? "bg-rail text-white" : "bg-white text-soft"}`}>
      {state === "finished" ? "✓" : "·"}
    </span>
  );
}

// A round badge with the hospital's letter.
function Letter({ letter, onGreen = false }: { letter: string; onGreen?: boolean }) {
  return (
    <span aria-hidden="true" className={`inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-lg font-semibold ${onGreen ? "bg-white text-rail" : "bg-mint text-rail"}`}>
      {letter}
    </span>
  );
}

export default function UploadReplay({ walkthrough, merged, notes }: { walkthrough: Walkthrough; merged: MergedSummary | null; notes: MergeNote[] }) {
  const hospitals = walkthrough.hospitals;
  const ready = hospitals.filter((h) => h.state === "ready");
  const canMerge = ready.length === hospitals.length && ready.length > 0;

  // When Start was pressed (ms), and how long ago that was. null = not started.
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState<number | null>(null);

  // What the right-hand panel shows: one hospital's record, or what the merge did.
  // It starts on the last hospital in the list (for the demo patient that is Hospital C,
  // the brand-name sheet), as in T68 item 27.
  const [chosen, setChosen] = useState<string>(ready[ready.length - 1]?.hospital ?? hospitals[0]?.hospital ?? "merge");

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

  // T68 item 26: when the replay ends, bring the "record is ready" card into view and put
  // the keyboard on its button, so the next step is obvious (and on camera).
  const readyRef = useRef<HTMLDivElement>(null);
  const openRef = useRef<HTMLAnchorElement>(null);
  useEffect(() => {
    if (!finished || !canMerge) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    readyRef.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "nearest" });
    openRef.current?.focus({ preventScroll: true });
  }, [finished, canMerge]);

  const start = () => {
    const now = Date.now();
    setStartedAt(now);
    setElapsed(0);
  };

  const recordsDone = elapsed !== null && elapsed >= lastRecordEnd;
  const mergeState: StepState = canMerge ? stateAt(elapsed, mergeStart, mergeEnd) : "waiting";

  // One state for each of the four steps across all records: done when every record has
  // done it, running while any record is on it.
  const stepStates: StepState[] = [0, 1, 2].map((i) => {
    const states = ready.map((h) => stateAt(elapsed, scheduleFor(h)[i].start, scheduleFor(h)[i].end));
    if (states.length > 0 && states.every((s) => s === "finished")) return "finished";
    return states.some((s) => s !== "waiting") ? "running" : "waiting";
  });
  stepStates.push(mergeState);

  // What one hospital's card says right now, in words.
  const hospitalLine = (h: WalkthroughHospital): string => {
    if (h.state === "not_run") return "Not run through the tool yet";
    const sched = scheduleFor(h);
    if (elapsed === null) return "Waiting for the replay";
    if (elapsed >= sched[2].end) return `${h.facts.length} facts read`;
    const i = sched.findIndex((s) => elapsed < s.end);
    return `${STEPS[i].doing}…`;
  };
  const hospitalDone = (h: WalkthroughHospital) => h.state === "ready" && elapsed !== null && elapsed >= scheduleFor(h)[2].end;

  // One short line for screen readers, so they hear progress without every step.
  const spoken =
    elapsed === null
      ? ""
      : finished && canMerge
        ? "The record is ready."
        : recordsDone
          ? "All three records checked. Merging."
          : "Reading all three records.";

  const factsIn = ready.reduce((n, h) => n + h.facts.length, 0);
  const picked = hospitals.find((h) => h.hospital === chosen);

  // The right-hand panel.
  const aside = (
    <>
      {picked ? (
        <>
          <div className="flex items-center gap-3">
            <Letter letter={picked.hospital} />
            <div>
              <h2 className="text-lg font-medium">Hospital {picked.hospital}</h2>
              <p className="text-sm text-soft">
                {picked.format}. File: {picked.file}
              </p>
            </div>
          </div>
          <section aria-label="The record as written">
            <h3 className="text-lg font-medium">As written</h3>
            <RecordText text={picked.record_text} file={picked.file} format={picked.format} />
          </section>
          <section aria-label="What the tool read">
            <h3 className="text-lg font-medium">Read as</h3>
            {picked.state === "not_run" ? (
              <p className="mt-2 rounded-2xl bg-mint px-4 py-3 text-soft">This record has not been run through the tool yet, so there is nothing to replay.</p>
            ) : !hospitalDone(picked) ? (
              <p className="mt-2 rounded-2xl bg-mint px-4 py-3 text-soft">
                {elapsed === null ? "Press the replay button to see what the tool read from this record." : `${hospitalLine(picked)}`}
              </p>
            ) : (
              <>
                <ul className="mt-2 flex flex-col gap-2">
                  {picked.facts.map((f) => {
                    const detail = factDetail(f);
                    return (
                      <li key={f.fact_id} className="flex items-baseline gap-3">
                        <span aria-hidden="true" className={`mt-1 h-2.5 w-2.5 shrink-0 self-start translate-y-1 rounded-full ${f.status === "stopped" || (f.type === "allergy" && f.status === "current") ? "bg-alert" : "bg-rail"}`} />
                        <span className="flex-1 font-normal">
                          {factName(f)}
                          {detail && <span className="text-soft">, {detail}</span>}
                        </span>
                        <span className="text-sm text-soft">{statusLabel(f)}</span>
                      </li>
                    );
                  })}
                </ul>
                {picked.retried && <p className="mt-2 text-sm text-soft">The Check step asked for one retry on this record.</p>}
                <details className="mt-3 text-sm">
                  <summary className="underline underline-offset-2">Show each fact with its quote</summary>
                  <div className="mt-2">
                    <FactList facts={picked.facts} />
                  </div>
                </details>
              </>
            )}
          </section>
        </>
      ) : (
        <section aria-label="What the merge did">
          <h2 className="text-lg font-medium">What the merge did</h2>
          <p className="mt-1 text-sm text-soft">
            {factsIn} facts went in. Facts that say the same thing were joined, each keeping all its sources{merged ? `, leaving ${merged.facts}` : ""}.
          </p>
          <ul className="mt-3 flex flex-col divide-y divide-sage">
            {notes.map((n, i) => (
              <li key={i} className="py-3">
                <p className="font-medium">{n.title}</p>
                <p>{n.text}</p>
              </li>
            ))}
          </ul>
        </section>
      )}
      <details className="mt-auto text-sm">
        <summary className="underline underline-offset-2">The four steps</summary>
        <ol className="mt-2 flex flex-col gap-2 list-decimal pl-5">
          {STEPS.map((s) => (
            <li key={s.key}>
              <span className="font-medium">{s.label}.</span> {s.what}
            </li>
          ))}
        </ol>
      </details>
    </>
  );

  return (
    <Page aside={aside} asideLabel="The chosen record">
      <Card className="flex flex-col gap-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex-1 basis-72">
            <h1 className="text-2xl font-medium leading-tight">Three hospital records, read into one</h1>
            <p className="mt-2 text-soft">
              Patient {walkthrough.patient_id}. Each hospital sent its record in a different format.
            </p>
          </div>
          <div className="flex flex-col items-end gap-1">
            <button type="button" onClick={start} disabled={elapsed !== null && !finished} className="rounded-full bg-rail px-5 py-2.5 text-white font-medium disabled:opacity-60">
              {/* T68 item 25: the button says it is a replay. */}
              {elapsed === null ? "Replay: read all three records" : finished ? "Replay again" : "Playing…"}
            </button>
            <p aria-live="polite" className="text-sm font-medium">
              {spoken}
            </p>
          </div>
        </div>
        <ol className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {STEPS.map((s, i) => (
            <li key={s.key}>
              <Tip className="w-full" tip={s.what}>
                <span className={`flex w-full items-center gap-2 rounded-2xl px-3 py-2 ${stepStates[i] === "waiting" ? "bg-mint text-soft" : "bg-leaf text-rail-ink"}`}>
                  <Mark state={stepStates[i]} />
                  <span className="flex flex-col leading-tight">
                    <span className="font-medium">{s.label}</span>
                    <span className="text-xs">{STATE_WORD[stepStates[i]]}</span>
                  </span>
                </span>
              </Tip>
            </li>
          ))}
        </ol>
        {/* The honest note about what this screen is (T28). */}
        <p className="text-sm text-soft">
          This screen replays a saved run. Live upload is switched off on this public page, so nothing you do here is
          sent to an AI. What you see is the tool&rsquo;s real, saved reading of these records.
        </p>
      </Card>

      <div className="grid gap-5 sm:grid-cols-3">
        {hospitals.map((h) => {
          const on = chosen === h.hospital;
          return (
            <button
              key={h.hospital}
              type="button"
              onClick={() => setChosen(h.hospital)}
              aria-pressed={on}
              className={`flex flex-col items-start gap-1 rounded-3xl p-5 text-left ${on ? "bg-rail text-white" : "bg-white hover:bg-leaf"}`}
            >
              <Letter letter={h.hospital} onGreen={on} />
              <span className="mt-2 text-lg font-medium leading-tight">
                <span className="sr-only">Hospital {h.hospital}: </span>
                {h.format}
              </span>
              <span className={`text-sm ${on ? "" : "text-soft"}`}>{hospitalLine(h)}</span>
            </button>
          );
        })}
      </div>

      <Card className={`flex flex-wrap items-center justify-between gap-4 ${chosen === "merge" ? "ring-4 ring-rail" : ""}`}>
        <div ref={readyRef} role="status" className="flex-1 basis-72">
          {finished && canMerge ? (
            <>
              <p className="text-3xl font-medium leading-tight">
                {factsIn} facts in{merged ? `, ${merged.facts} out` : ""}
              </p>
              <p className="mt-1 text-soft">
                The record is ready
                {merged ? `: ${merged.facts} facts and ${merged.conflicts} ${merged.conflicts === 1 ? "disagreement" : "disagreements"} for the doctor to see.` : "."}
              </p>
            </>
          ) : (
            <>
              <p className="text-lg font-medium">Merge</p>
              <p className="mt-1 flex items-center gap-2 text-soft">
                <Mark state={mergeState} />
                {!canMerge
                  ? "Needs all three records to be run first."
                  : mergeState === "running"
                    ? "Merging the three readings into one record with the six rules…"
                    : "Waits for all three records, then joins them with the six rules."}
              </p>
            </>
          )}
        </div>
        {finished && canMerge && (
          <div className="flex flex-wrap items-center gap-3">
            {notes.length > 0 && (
              <button type="button" onClick={() => setChosen("merge")} aria-pressed={chosen === "merge"} className="rounded-full bg-mint px-5 py-2.5 font-medium text-rail-ink">
                What the merge did
              </button>
            )}
            <Link ref={openRef} href={`/?id=${walkthrough.patient_id}`} className="rounded-full bg-rail px-6 py-3 text-lg font-medium text-white hover:bg-rail-ink">
              Open the doctor screen for {walkthrough.patient_id}
            </Link>
          </div>
        )}
      </Card>
    </Page>
  );
}
