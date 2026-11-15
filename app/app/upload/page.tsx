// Hospital upload screen (T28). Replays a saved run of the tool on the demo patient's
// three hospital records: which step is running, then the facts read from each record.
// Reads app/data/walkthrough_<ID>.json only. No model calls, no key (CLAUDE.md app rules).
import { Suspense } from "react";
import { loadWalkthrough, WALKTHROUGH_ID } from "@/lib/walkthrough";
import UploadReplay from "./UploadReplay";

export const metadata = { title: "Hospital upload · Handover" };

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
  return <UploadReplay walkthrough={load.walkthrough} />;
}

export default function UploadPage() {
  return (
    <main className="flex-1 p-4 sm:p-8 max-w-5xl w-full mx-auto">
      <h1 className="text-3xl font-semibold">Hospital upload</h1>
      <p className="mt-2">
        Staff at each hospital send in their record for patient {WALKTHROUGH_ID}. The three hospitals use
        three different formats: a table, a free-text letter and a sheet with brand names.
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
