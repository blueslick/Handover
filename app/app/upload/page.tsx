// Hospital upload screen (T28, upgraded in T63). Replays a saved run of the tool on the
// demo patient's three hospital records: all three move through Read, Extract and Check at
// the same time, then one Merge step, then the record is ready.
// Reads app/data/walkthrough_<ID>.json and app/data/index.json only. No model calls, no key
// (CLAUDE.md app rules).
import { Suspense } from "react";
import { loadWalkthrough, WALKTHROUGH_ID } from "@/lib/walkthrough";
import publishedIndex from "../../data/index.json";
import UploadReplay, { type MergedSummary } from "./UploadReplay";

export const metadata = { title: "Hospital records (replay) · Handover" };

async function Replay() {
  const load = await loadWalkthrough(WALKTHROUGH_ID);

  if (load.state === "missing") {
    return (
      <div role="alert" className="mt-6 border-2 border-zinc-700 rounded p-4">
        <p className="font-semibold">No saved run to replay yet.</p>
        <p className="mt-1">The upload replay appears once the tool has been run on the demo patient.</p>
      </div>
    );
  }
  if (load.state === "failed") {
    return (
      <div role="alert" className="mt-6 border-4 border-amber-700 bg-amber-50 text-amber-950 rounded p-4">
        <p className="font-bold">The saved run could not be loaded.</p>
        <p className="mt-1">The file is damaged, so nothing is shown rather than part of it.</p>
      </div>
    );
  }
  // The merged record's counts, only if the app's record comes from the same saved run.
  const w = load.walkthrough;
  const entry = publishedIndex.patients.find((p) => p.patient_id === w.patient_id);
  const merged: MergedSummary | null =
    entry && publishedIndex.compiled_run_id === w.run_id ? { facts: entry.facts, conflicts: entry.conflicts } : null;
  return <UploadReplay walkthrough={w} merged={merged} />;
}

export default function UploadPage() {
  return (
    <main className="flex-1 p-4 sm:p-8 max-w-5xl w-full mx-auto">
      <h1 className="text-3xl font-semibold">Hospital records (replay)</h1>
      <p className="mt-2">
        How the tool reads one patient&rsquo;s records: three hospitals each sent a record for patient{" "}
        {WALKTHROUGH_ID}, in three different formats: a table, a free-text letter and a sheet with brand names.
      </p>
      <div className="mt-4 border-2 border-zinc-700 bg-zinc-50 rounded p-4">
        <p className="font-bold">This screen replays a saved run.</p>
        <p className="mt-1">
          Live upload is switched off on this public page, so nothing you do here is sent to an AI. What you see
          is the tool&rsquo;s real, saved reading of these records.
        </p>
      </div>
      <Suspense fallback={<p className="mt-6">Loading…</p>}>
        <Replay />
      </Suspense>
    </main>
  );
}
