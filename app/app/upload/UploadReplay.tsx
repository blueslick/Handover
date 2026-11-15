"use client";
// Records replay (T28, T63; laid out as tabs in T81). Replays a saved run of the tool on
// the demo patient's three hospital records. Each record has its own tab: the record as
// written on the left, what the tool read from it on the right, and the four steps
// (Read, Extract, Check, Merge) in a slim row above. All three records go through the
// first three steps together, then one Merge step joins them.
// It replays a saved run: every number shown comes from the saved files. The pauses are
// only for watching; nothing is sent to an AI from this page.
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { Walkthrough, WalkthroughHospital } from "@/lib/walkthrough";
import { FREQUENCY_LABELS, FLAG_LABELS, statusLabel } from "@/lib/labels";
import { hospitalFull, hospitalShort } from "@/lib/hospitals";
import { factName } from "@/lib/names";
import type { Fact } from "@/lib/types";
import Page, { Box } from "../components/Page";
import Tag from "../components/Tag";
import RecordText from "./RecordText";

export interface MergedSummary {
  facts: number;
  conflicts: number;
}

export interface MergeNote {
  title: string;
  text: string;
}

type StepState = "waiting" | "running" | "finished";
const STATE_WORD: Record<StepState, string> = { waiting: "waiting", running: "running now", finished: "done" };

// How long each step is shown for, in milliseconds. Display only.
const READ_MS = 900;
const CHECK_MS = 1300;
const MERGE_MS = 1800;
function extractMs(h: WalkthroughHospital) {
  const out = h.tokens?.output_tokens ?? 400;
  return 1200 + Math.min(out, 1000) * 4;
}

const STEPS = [
  { key: "read", label: "Read", doing: "Reading the record", what: "Open each hospital's record." },
  { key: "extract", label: "Extract", doing: "Extracting the facts with AI", what: "The AI (Claude) lists every fact with the exact words it came from." },
  { key: "check", label: "Check", doing: "Checking every fact against the record's own words", what: "Code checks each fact against the record's own words and looks up each brand name in a fixed table. No AI. A fact that fails is kept and labelled, never dropped." },
  { key: "merge", label: "Merge", doing: "Merging", what: "Six written rules join the three lists into one record. No AI." },
] as const;

// When each of the first three steps starts and ends for one record.
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

// The record's layout in one word, from the saved run's own description.
function formatWord(format: string): string {
  const f = format.toLowerCase();
  if (f.includes("table")) return "Table";
  if (f.includes("letter")) return "Letter";
  if (f.includes("sheet")) return "Medication sheet";
  return format;
}

// What kind of fact a row is, in a doctor's words.
const TYPE_WORD: Record<Fact["type"], string> = { allergy: "Allergy", medicine: "Medicine", diagnosis: "Problem", operation: "Operation" };

export default function UploadReplay({ walkthrough, merged, notes, banner }: { walkthrough: Walkthrough; merged: MergedSummary | null; notes: MergeNote[]; banner?: React.ReactNode }) {
  const hospitals = walkthrough.hospitals;
  const ready = hospitals.filter((h) => h.state === "ready");
  const canMerge = ready.length === hospitals.length && ready.length > 0;

  // The replay clock: null before the button is pressed.
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState<number | null>(null);
  // Which record's tab is open. Starts on the last record that has a saved reading.
  const [chosen, setChosen] = useState<string>(ready[ready.length - 1]?.hospital ?? hospitals[0]?.hospital ?? "");

  const lastRecordEnd = Math.max(0, ...ready.map((h) => scheduleFor(h)[2].end));
  const mergeStart = lastRecordEnd;
  const mergeEnd = mergeStart + MERGE_MS;
  const finished = elapsed !== null && elapsed >= (canMerge ? mergeEnd : lastRecordEnd);

  useEffect(() => {
    if (startedAt === null || finished) return;
    const timer = setInterval(() => setElapsed(Date.now() - startedAt), 150);
    return () => clearInterval(timer);
  }, [startedAt, finished]);

  // When the record is ready, bring the result into view and move the keyboard to the link.
  const readyRef = useRef<HTMLDivElement>(null);
  const openRef = useRef<HTMLAnchorElement>(null);
  useEffect(() => {
    if (!finished || !canMerge) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    readyRef.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "nearest" });
    openRef.current?.focus({ preventScroll: true });
  }, [finished, canMerge]);

  const start = () => {
    setStartedAt(Date.now());
    setElapsed(0);
  };

  const recordsDone = elapsed !== null && elapsed >= lastRecordEnd;
  const mergeState: StepState = canMerge ? stateAt(elapsed, mergeStart, mergeEnd) : "waiting";

  const picked = hospitals.find((h) => h.hospital === chosen) ?? hospitals[0];
  const pickedDone = picked?.state === "ready" && elapsed !== null && elapsed >= scheduleFor(picked)[2].end;

  // The state of each of the four steps for the record whose tab is open.
  const stepStates: StepState[] = picked?.state === "ready" ? scheduleFor(picked).map((s) => stateAt(elapsed, s.start, s.end)) : ["waiting", "waiting", "waiting"];
  stepStates.push(mergeState);

  // The short note beside each step, from the saved run.
  const verified = picked ? picked.facts.filter((f) => !f.flags.includes("unverified")).length : 0;
  const stepNote = [
    "",
    pickedDone ? `${picked.facts.length} facts, by AI` : "by AI",
    pickedDone ? `${verified} of ${picked.facts.length} matched` : "",
    "with the other records",
  ];

  // What the open record is doing right now, in words.
  const pickedLine = (): string => {
    if (!picked) return "";
    if (picked.state === "not_run") return "This record has not been run through the tool yet, so there is nothing to replay.";
    if (elapsed === null) return "Press Replay to see what the tool read from this record.";
    const sched = scheduleFor(picked);
    const i = sched.findIndex((s) => elapsed < s.end);
    return i < 0 ? "" : `${STEPS[i].doing}…`;
  };

  // Said aloud by screen readers as the replay moves on.
  const spoken = elapsed === null ? "" : finished && canMerge ? "The record is ready." : recordsDone ? "All three records checked. Merging." : "Reading all three records.";

  const factsIn = ready.reduce((n, h) => n + h.facts.length, 0);
  const anyFlags = pickedDone && picked.facts.some((f) => f.flags.length > 0);

  const bar = (
    <p role="note" className="border-b border-line bg-accent-tint px-4 py-1.5 text-xs sm:px-6">
      <span className="font-semibold">Saved replay of a real run.</span> Nothing here is sent to an AI.
    </p>
  );

  return (
    <Page banner={banner} bar={bar}>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <h1 className="text-xl font-semibold">Hospital records</h1>
        <p aria-live="polite" className="text-quiet">
          {spoken}
        </p>
        <button type="button" onClick={start} disabled={elapsed !== null && !finished} className="ml-auto h-8 rounded-ctl border border-accent bg-accent px-3 font-medium text-white disabled:opacity-60">
          {/* T68 item 25: the button says it is a replay. */}
          {elapsed === null ? "Replay: read all three records" : finished ? "Replay from the start" : "Playing…"}
        </button>
      </div>

      <section aria-label="The three records" className="rounded-box border border-line bg-surface">
        {/* One tab per hospital record. */}
        <div role="tablist" aria-label="Hospital record" className="flex flex-wrap border-b border-line px-1">
          {hospitals.map((h) => {
            const on = h.hospital === picked?.hospital;
            return (
              <button
                key={h.hospital}
                type="button"
                role="tab"
                aria-selected={on}
                onClick={() => setChosen(h.hospital)}
                className={`flex min-h-12 flex-col justify-center border-b-2 px-4 py-1 text-left ${on ? "border-accent text-ink" : "border-transparent text-quiet hover:text-ink"}`}
              >
                <span className="font-semibold">{hospitalFull(h.hospital)}</span>
                <span className="text-xs">{formatWord(h.format)}</span>
              </button>
            );
          })}
        </div>

        {/* The four steps, in order, each with its state in words. */}
        <ol aria-label="Steps" className="grid grid-cols-2 border-b border-line bg-panel md:grid-cols-4">
          {STEPS.map((s, i) => (
            <li key={s.key} title={s.what} className="flex min-h-10 flex-wrap items-center gap-x-2 border-line px-3 py-1 md:border-r md:last:border-r-0">
              <span className={stepStates[i] === "waiting" ? "text-quiet" : "font-semibold"}>
                {i + 1}. {s.label}
              </span>
              {stepNote[i] && <span className="text-quiet">{stepNote[i]}</span>}
              <span className={`ml-auto text-xs ${stepStates[i] === "running" ? "font-semibold text-accent" : "text-quiet"}`}>{STATE_WORD[stepStates[i]]}</span>
            </li>
          ))}
        </ol>

        {picked && (
          <div className="flex flex-col lg:flex-row">
            <div className="flex min-w-0 flex-1 flex-col gap-2 border-line p-3 lg:border-r">
              <h2 className="font-semibold">Record as written{pickedDone && ", sources highlighted"}</h2>
              <RecordText text={picked.record_text} quotes={pickedDone ? picked.facts.map((f) => f.quote) : []} />
            </div>
            <div className="flex min-w-0 flex-[1.2] flex-col gap-2 py-3">
              <p className="flex flex-wrap items-baseline gap-2 px-3">
                <span className="font-semibold">Extracted reading</span>
                <span className="text-quiet">Read by AI</span>
              </p>
              {!pickedDone ? (
                <p className="px-3 text-quiet">{pickedLine()}</p>
              ) : (
                <>
                  <table className="dt stack">
                    <thead>
                      <tr>
                        <th scope="col">Type</th>
                        <th scope="col">As written</th>
                        <th scope="col">Read as</th>
                        <th scope="col">Dose</th>
                        <th scope="col">Frequency</th>
                        <th scope="col">Status</th>
                        {anyFlags && <th scope="col">Check</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {picked.facts.map((f) => (
                        <tr key={f.fact_id} className={f.flags.length > 0 ? "row-warn" : ""}>
                          <td>{TYPE_WORD[f.type]}</td>
                          <td className="font-mono text-xs">{f.name_as_written ?? ""}</td>
                          <td className={f.status === "none_recorded" ? "" : "font-semibold"}>{factName(f)}</td>
                          <td>{f.dose ?? ""}</td>
                          <td>{f.frequency ? (FREQUENCY_LABELS[f.frequency] ?? f.frequency) : ""}</td>
                          <td>{f.status === "none_recorded" ? "None recorded" : statusLabel(f)}</td>
                          {anyFlags && (
                            <td>
                              <span className="flex flex-wrap gap-1">
                                {f.flags.map((flag) => (
                                  <Tag key={flag} kind="warn">
                                    {FLAG_LABELS[flag]}
                                  </Tag>
                                ))}
                              </span>
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {picked.retried && <p className="px-3 text-quiet">The Check step asked for one retry on this record.</p>}
                </>
              )}
              <details className="mx-3 border-t border-line pt-2">
                <summary className="font-semibold">Details: the four steps</summary>
                <ol className="mt-2 flex list-decimal flex-col gap-1 pl-5">
                  {STEPS.map((s) => (
                    <li key={s.key}>
                      <span className="font-medium">{s.label}.</span> {s.what}
                    </li>
                  ))}
                </ol>
              </details>
            </div>
          </div>
        )}
      </section>

      <Box title="Merge result" id="merge-result" right="Fixed rules, no AI">
        <div ref={readyRef} role="status">
          {finished && canMerge ? (
            <>
              <table className="dt">
                <thead>
                  <tr>
                    <th scope="col">From</th>
                    <th scope="col" className="num">Facts read</th>
                  </tr>
                </thead>
                <tbody>
                  {ready.map((h) => (
                    <tr key={h.hospital}>
                      <td title={hospitalFull(h.hospital)}>{hospitalShort(h.hospital)}</td>
                      <td className="num">{h.facts.length}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {notes.length > 0 && (
                <ul className="border-t border-line">
                  {notes.map((n, i) => (
                    <li key={i} className="border-b border-line px-3 py-1.5 last:border-b-0">
                      <span className="font-medium">{n.title}.</span> {n.text}
                    </li>
                  ))}
                </ul>
              )}
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line px-3 py-2">
                <p>
                  <span className="font-semibold">
                    Record ready: {factsIn} facts in{merged ? `, ${merged.facts} lines out` : ""}.
                  </span>
                  {merged && ` ${merged.conflicts} ${merged.conflicts === 1 ? "disagreement" : "disagreements"} kept for the doctor.`}
                </p>
                <Link ref={openRef} href={`/?id=${walkthrough.patient_id}`} className="ml-auto inline-flex h-8 items-center rounded-ctl border border-accent bg-accent px-3 font-medium text-white">
                  Open the doctor screen
                </Link>
              </div>
            </>
          ) : (
            <p className="px-3 py-2 text-quiet">
              {!canMerge
                ? "Needs all three records to be run first."
                : mergeState === "running"
                  ? "Merging the three readings into one record with the six rules…"
                  : "Waits for all three records, then joins them with the six rules."}
            </p>
          )}
        </div>
      </Box>
    </Page>
  );
}
