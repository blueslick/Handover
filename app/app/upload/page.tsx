// Hospital records screen (T28, upgraded in T63, new look in T75). Replays a saved run of
// the tool on the demo patient's three hospital records: all three move through Read,
// Extract and Check at the same time, then one Merge step, then the record is ready.
// Reads app/data/walkthrough_<ID>.json, the patient's merged record and app/data/index.json
// only. No model calls, no key (CLAUDE.md app rules).
import { Suspense } from "react";
import { loadWalkthrough, WALKTHROUGH_ID, type Walkthrough } from "@/lib/walkthrough";
import { loadRecordState } from "@/lib/records";
import { bannerLines, doseChange } from "@/lib/banner";
import { formatDate } from "@/lib/dates";
import { capitalise, factName } from "@/lib/names";
import type { Fact } from "@/lib/types";
import publishedIndex from "../../data/index.json";
import Page, { Card } from "../components/Page";
import UploadReplay, { type MergedSummary, type MergeNote } from "./UploadReplay";

export const metadata = { title: "Hospital records (replay) · Handover" };

// What the Merge step did for this patient, in plain words, worked out from the saved
// reading of each record and the merged record (never typed by hand).
function mergeNotes(w: Walkthrough, merged: Fact[]): MergeNote[] {
  const notes: MergeNote[] = [];
  // Brand names the hospitals wrote, next to the generic name the record shows.
  const brands = new Map<string, string>();
  for (const h of w.hospitals) {
    for (const f of h.facts) {
      const written = f.name_as_written ?? "";
      if (f.status !== "none_recorded" && f.name && written && written.toLowerCase() !== f.name.toLowerCase()) {
        brands.set(written, f.name);
      }
    }
  }
  if (brands.size > 0) {
    notes.push({ title: "Brand names made generic", text: [...brands].map(([b, g]) => `${b} to ${g}.`).join(" ") });
  }
  for (const f of merged) {
    if (f.type === "medicine" && f.status === "stopped" && !f.conflict_group) {
      const was = f.history.find((h) => h.status === "current");
      notes.push({
        title: "A stop is kept",
        text: `${factName(f)}${was ? ` was current at Hospital ${was.hospital} (${formatDate(was.date)}) and` : ""} was stopped at Hospital ${f.hospital} (${formatDate(f.date)}). It shows as stopped.`,
      });
    }
    const change = f.flags.includes("dose_changed") ? doseChange(f) : null;
    if (change) {
      notes.push({ title: "A dose change is kept", text: `${capitalise(f.name ?? "")} went from ${change.from} to ${change.to}. The newer dose shows; the older one stays in the history.` });
    }
  }
  for (const l of bannerLines(merged).filter((l) => l.key.startsWith("conflict-"))) {
    notes.push({ title: "A disagreement is kept", text: `${l.text.slice(l.text.indexOf(": ") + 2)} Both go to the doctor.` });
  }
  return notes;
}

async function Replay() {
  const load = await loadWalkthrough(WALKTHROUGH_ID);

  if (load.state === "missing") {
    return (
      <Page>
        <Card role="alert">
          <p className="font-medium">No saved run to replay yet.</p>
          <p className="mt-1">The replay appears once the tool has been run on the demo patient.</p>
        </Card>
      </Page>
    );
  }
  if (load.state === "failed") {
    return (
      <Page>
        <Card role="alert" className="border-4 border-alert">
          <p className="font-medium">The saved run could not be loaded.</p>
          <p className="mt-1">The file is damaged, so nothing is shown rather than part of it.</p>
        </Card>
      </Page>
    );
  }
  // The merged record's counts and notes, only if the app's record comes from the same saved run.
  const w = load.walkthrough;
  const entry = publishedIndex.patients.find((p) => p.patient_id === w.patient_id);
  const sameRun = entry && publishedIndex.compiled_run_id === w.run_id;
  const merged: MergedSummary | null = sameRun ? { facts: entry.facts, conflicts: entry.conflicts } : null;
  const record = sameRun ? await loadRecordState(w.patient_id, "handover") : null;
  const notes = record?.state === "ok" && record.record.run_id === w.run_id ? mergeNotes(w, record.record.facts) : [];
  return <UploadReplay walkthrough={w} merged={merged} notes={notes} />;
}

export default function UploadPage() {
  return (
    <Suspense
      fallback={
        <Page>
          <p>Loading…</p>
        </Page>
      }
    >
      <Replay />
    </Suspense>
  );
}
