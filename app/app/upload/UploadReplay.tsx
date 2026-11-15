"use client";
// The moving part of the upload screen (T28). Pick a hospital, press "Read this record",
// and the steps play one after another, then the facts the tool read appear.
// It replays a saved run: the pauses are only there so each step can be seen.
import Link from "next/link";
import { useEffect, useState } from "react";
import type { Walkthrough, WalkthroughHospital } from "@/lib/walkthrough";
import FactList from "../components/FactList";

type Stage = "idle" | "reading" | "checking" | "done";

// How long each step stays on screen in the replay, in milliseconds.
const READING_MS = 2500;
const CHECKING_MS = 1500;

const STEPS: { stage: Exclude<Stage, "idle">; label: string }[] = [
  { stage: "reading", label: "Reading the record with Claude" },
  { stage: "checking", label: "Checking every fact against the record's own words" },
  { stage: "done", label: "Done" },
];
const ORDER: Stage[] = ["idle", "reading", "checking", "done"];

// One line of the step list: waiting, running now, or finished, said in words.
function StepLine({ label, state }: { label: string; state: "waiting" | "running" | "finished" }) {
  return (
    <li className="flex items-center gap-2">
      {state === "running" ? (
        <span
          aria-hidden="true"
          className="inline-block h-4 w-4 rounded-full border-2 border-zinc-800 border-t-transparent motion-safe:animate-spin"
        />
      ) : (
        <span aria-hidden="true" className="inline-block w-4 text-center font-bold">
          {state === "finished" ? "✓" : "·"}
        </span>
      )}
      <span className={state === "running" ? "font-semibold" : state === "waiting" ? "text-zinc-600" : ""}>
        {label}
        <span className="text-sm">
          {state === "running" ? " (running now)" : state === "finished" ? " (finished)" : " (waiting)"}
        </span>
      </span>
    </li>
  );
}

function HospitalPanel({
  h,
  stage,
  onStart,
}: {
  h: WalkthroughHospital;
  stage: Stage;
  onStart: () => void;
}) {
  const at = ORDER.indexOf(stage);
  return (
    <section aria-label={`Hospital ${h.hospital}`} className="mt-4">
      <h2 className="text-xl font-semibold">
        Hospital {h.hospital}: {h.format}
      </h2>
      <p className="text-sm text-zinc-700">File: {h.file}</p>
      <pre className="mt-2 max-h-72 overflow-auto border border-zinc-400 rounded bg-zinc-50 p-3 text-xs whitespace-pre-wrap break-words">
        {h.record_text}
      </pre>

      {h.state === "not_run" ? (
        <p role="status" className="mt-3 border-2 border-zinc-700 rounded p-3">
          This record has not been run through the tool yet, so there is nothing to replay.
        </p>
      ) : (
        <>
          {stage === "idle" && (
            <button
              type="button"
              onClick={onStart}
              className="mt-3 border border-zinc-800 bg-zinc-800 text-white rounded px-4 py-2"
            >
              Read this record
            </button>
          )}
          {stage !== "idle" && (
            <ol aria-live="polite" className="mt-3 flex flex-col gap-1">
              {STEPS.map((s) => {
                const i = ORDER.indexOf(s.stage);
                const state =
                  i < at || (s.stage === "done" && stage === "done") ? "finished" : i === at ? "running" : "waiting";
                const label =
                  s.stage === "done" && stage === "done"
                    ? `Done: ${h.facts.length} facts read, each with its quote${h.retried ? " (the Check step asked for one retry)" : ""}`
                    : s.label;
                return <StepLine key={s.stage} label={label} state={state} />;
              })}
            </ol>
          )}
          {stage === "done" && (
            <div className="mt-4">
              <h3 className="text-lg font-semibold mb-2">What the tool read from Hospital {h.hospital}</h3>
              <FactList facts={h.facts} />
            </div>
          )}
        </>
      )}
    </section>
  );
}

export default function UploadReplay({ walkthrough }: { walkthrough: Walkthrough }) {
  const hospitals = walkthrough.hospitals;
  const [selected, setSelected] = useState(hospitals[0]?.hospital ?? "A");
  const [stages, setStages] = useState<Record<string, Stage>>(
    Object.fromEntries(hospitals.map((h) => [h.hospital, "idle" as Stage])),
  );

  // Moves a running hospital on to its next step after a pause.
  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = [];
    for (const [h, stage] of Object.entries(stages)) {
      if (stage === "reading") {
        timers.push(setTimeout(() => setStages((s) => ({ ...s, [h]: "checking" })), READING_MS));
      } else if (stage === "checking") {
        timers.push(setTimeout(() => setStages((s) => ({ ...s, [h]: "done" })), CHECKING_MS));
      }
    }
    return () => timers.forEach(clearTimeout);
  }, [stages]);

  const current = hospitals.find((h) => h.hospital === selected) ?? hospitals[0];
  const ready = hospitals.filter((h) => h.state === "ready");
  const allDone = ready.length > 0 && ready.every((h) => stages[h.hospital] === "done");

  return (
    <div>
      <nav aria-label="Choose a hospital record" className="mt-6">
        <p className="font-medium">Hospital record:</p>
        <ul className="mt-1 flex flex-wrap gap-2">
          {hospitals.map((h) => {
            const isCurrent = h.hospital === selected;
            const stage = stages[h.hospital];
            const note = h.state === "not_run" ? "not run yet" : stage === "done" ? "read" : stage === "idle" ? "not read" : "reading";
            return (
              <li key={h.hospital}>
                <button
                  type="button"
                  aria-pressed={isCurrent}
                  onClick={() => setSelected(h.hospital)}
                  className={`border-2 border-zinc-800 rounded px-3 py-2 text-left ${
                    isCurrent ? "bg-zinc-800 text-white font-semibold" : "bg-white underline"
                  }`}
                >
                  Hospital {h.hospital}
                  <span className="block text-xs">{note}{isCurrent ? ", showing now" : ""}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      {current && (
        <HospitalPanel
          key={current.hospital}
          h={current}
          stage={stages[current.hospital]}
          onStart={() => setStages((s) => ({ ...s, [current.hospital]: "reading" }))}
        />
      )}

      {allDone && (
        <div role="status" className="mt-6 border-2 border-zinc-800 rounded p-4">
          <p className="font-semibold">
            {ready.length === hospitals.length
              ? "All three records are read."
              : `${ready.length} of ${hospitals.length} records are read.`}{" "}
            The merge rules then combine them into one record.
          </p>
          <Link href={`/?id=${walkthrough.patient_id}`} className="mt-2 inline-block underline font-medium">
            See the merged record for {walkthrough.patient_id} on the doctor screen
          </Link>
        </div>
      )}
    </div>
  );
}
