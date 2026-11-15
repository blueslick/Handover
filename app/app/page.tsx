// Doctor screen. The patient ID comes from the address (/?id=D001).
// Reads JSON from app/data/ only: no model calls, no key.
import Link from "next/link";
import { Suspense } from "react";
import { isKnownId, liveRun, liveRuns, loadRecordState, parseView, SAMPLE_IDS, type LiveRun, type View } from "@/lib/records";
import type { Fact } from "@/lib/types";
import { loadOmission } from "@/lib/omission";
import { isOlderNoMedicinesLine } from "@/lib/olderRecord";
import FactList from "./components/FactList";
import OlderRecordNote from "./components/OlderRecordNote";
import OmissionBox from "./components/OmissionBox";
import WarningBanner from "./components/WarningBanner";

// A titled group of facts; renders nothing when empty.
function Section({ title, facts }: { title: string; facts: Fact[] }) {
  if (facts.length === 0) return null;
  return (
    <section className="mt-6">
      <h2 className="text-xl font-semibold mb-2">{title}</h2>
      <FactList facts={facts} />
    </section>
  );
}

// Links to the sample IDs, shown under the box and on the unknown-ID message.
// On Daniel's laptop, live runs (T58) are listed too; on the public link there are none.
function SampleIds() {
  const live = liveRuns();
  return (
    <>
      <p className="mt-2 text-sm">
        Sample IDs:{" "}
        {SAMPLE_IDS.map((id) => (
          <Link key={id} href={`/?id=${id}`} className="underline font-medium mr-2">
            {id}
          </Link>
        ))}
      </p>
      {live.length > 0 && (
        <p className="mt-1 text-sm">
          Live runs on this laptop:{" "}
          {live.map((p) => (
            <Link key={p.patient_id} href={`/?id=${p.patient_id}`} className="underline font-medium mr-2">
              {p.patient_id}
            </Link>
          ))}
        </p>
      )}
    </>
  );
}

// Shown above a live record (T58), so no one mistakes it for the saved demo run.
function LiveNote({ run }: { run: LiveRun }) {
  const made = new Date(run.made_at);
  const when = isNaN(made.getTime()) ? run.made_at : made.toLocaleString("en-GB");
  return (
    <div className="mt-4 border-2 border-zinc-800 bg-zinc-50 rounded p-4">
      <p className="font-bold">Live run on this laptop.</p>
      <p className="mt-1">
        Read just now by {run.model} at {when}, from these files: {run.source_files.join(", ")}. Each record
        went through the same steps as the tested tool: read by Claude, every fact checked against the
        record&rsquo;s own words, then merged with the six rules.
      </p>
      <p className="mt-1 text-sm">
        Tool: {run.tool}. Run {run.run_id}. This record stays on this laptop; the public link only replays a
        saved run.
      </p>
    </div>
  );
}

// The patient shown when the address has no ID (T68 item 2).
const DEFAULT_ID = SAMPLE_IDS.includes("D001") ? "D001" : (SAMPLE_IDS[0] ?? "");

type SearchParams = Promise<{ id?: string | string[]; view?: string | string[] }>;

// The two-way switch (T27). Two links, so it works without JavaScript and the
// address says which view is showing. The current choice is marked in words and
// with a solid fill, not by colour alone.
function ViewSwitch({ id, view }: { id: string; view: View }) {
  const options: { value: View; label: string; href: string }[] = [
    { value: "handover", label: "Handover (our tool)", href: `/?id=${encodeURIComponent(id)}` },
    { value: "baseline", label: "Baseline (keyword search)", href: `/?id=${encodeURIComponent(id)}&view=baseline` },
  ];
  return (
    <nav aria-label="Choose which record to show" className="mt-6">
      <p className="font-medium">Show:</p>
      <ul className="mt-1 inline-flex border-2 border-zinc-800 rounded overflow-hidden">
        {options.map((o) => {
          const current = o.value === view;
          return (
            <li key={o.value}>
              <Link
                href={o.href}
                aria-current={current ? "page" : undefined}
                className={`inline-block px-4 py-2 ${
                  current ? "bg-zinc-800 text-white font-semibold" : "bg-white text-zinc-900 underline"
                }`}
              >
                {o.label}
                {current && <span className="sr-only"> (showing now)</span>}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

// What the baseline is, shown above the baseline record so no one mistakes it for the tool's output.
function BaselineNote() {
  return (
    <div className="mt-4 border-2 border-zinc-700 bg-zinc-50 rounded p-4">
      <p className="font-bold">This is the baseline, not our tool.</p>
      <p className="mt-1">
        A simple keyword search read each hospital record and every line it found is listed, with no
        merging: no checking against the source, no conflict warnings, and no rule for which hospital
        is most recent. It is shown so you can compare it with the Handover record.
      </p>
    </div>
  );
}

// Looks up the ID and shows the record, a prompt (no ID yet) or the unknown-ID message.
async function Record({ searchParams }: { searchParams: SearchParams }) {
  const { id: rawId, view: rawView } = await searchParams;
  const typed = (Array.isArray(rawId) ? rawId[0] : rawId)?.trim() ?? "";
  const view = parseView(rawView);

  // T68 item 2: with no ID in the address, open the demo patient so the first
  // screen shows a record. If D001 is ever not published, use the first sample ID.
  const id = typed || DEFAULT_ID;
  if (!id) {
    return <p className="mt-6">Enter a patient ID above to see the merged record.</p>;
  }

  const load = await loadRecordState(id, view);

  // A known patient with no baseline file: keep the switch so the doctor can go back.
  if (view === "baseline" && load.state === "missing" && isKnownId(id)) {
    return (
      <>
        <ViewSwitch id={id} view={view} />
        <div role="alert" className="mt-6 border-2 border-zinc-700 rounded p-4">
          <p className="font-semibold">No baseline record for “{id}”.</p>
          <p className="mt-1">Switch back to Handover to see this patient&rsquo;s merged record.</p>
        </div>
      </>
    );
  }

  // Failed state: the patient is listed but the file could not be read.
  if (load.state === "failed") {
    return (
      <>
      <ViewSwitch id={id} view={view} />
      <div role="alert" className="mt-6 border-4 border-amber-700 bg-amber-50 text-amber-950 rounded p-4">
        <p className="font-bold">The record for “{id}” could not be loaded.</p>
        <p className="mt-1">The file is damaged, so nothing is shown rather than part of the record.</p>
      </div>
      </>
    );
  }

  if (load.state === "missing") {
    return (
      <div role="alert" className="mt-6 border-2 border-zinc-700 rounded p-4">
        <p className="font-semibold">No record found for “{id}”.</p>
        <p className="mt-1">Try one of the sample IDs: {SAMPLE_IDS.join(", ")}.</p>
      </div>
    );
  }

  const record = load.record;
  const facts = record.facts;
  const ofType = (t: Fact["type"]) => facts.filter((f) => f.type === t);
  // T67: in the Handover view, an older "no regular medicines" line moves to a greyed
  // history box when a later record lists current medicines. The baseline view lists
  // every line as found, so it is left alone.
  const olderMeds =
    view === "handover" ? ofType("medicine").filter((f) => isOlderNoMedicinesLine(f, facts)) : [];
  const meds = ofType("medicine").filter((f) => !olderMeds.includes(f));
  // Word-search hint (T64), Handover view only, and only from the same run as the record.
  const omission = view === "handover" ? await loadOmission(record.patient_id, record.run_id) : null;
  const live = view === "handover" ? liveRun(record.patient_id) : undefined;

  return (
    <>
    <ViewSwitch id={record.patient_id} view={view} />
    {view === "baseline" && <BaselineNote />}
    {live && <LiveNote run={live} />}
    <div className="mt-6">
      <h2 className="text-2xl font-semibold">
        Patient {record.patient_id}
        {view === "baseline" && <span className="font-normal">: baseline</span>}
      </h2>
      <p className="text-sm text-zinc-700">
        {view === "baseline"
          ? `Every line the keyword search found in ${record.built_from.length} hospital records: ${facts.length} entries.`
          : `Merged from ${record.built_from.length} hospital records: ${facts.length} facts.`}
      </p>
      <div className="mt-4">
        <WarningBanner facts={facts} />
      </div>
      <Section title="Allergies" facts={ofType("allergy")} />
      <Section title="Current medicines" facts={meds.filter((f) => f.status === "current")} />
      <Section title="Other medicines (stopped or planned)" facts={meds.filter((f) => f.status !== "current")} />
      <OlderRecordNote facts={olderMeds} />
      <Section title="Diagnoses" facts={ofType("diagnosis")} />
      <Section title="Operations" facts={ofType("operation")} />
      {omission && <OmissionBox load={omission} />}
    </div>
    </>
  );
}

// Keeps the chosen view when a new ID is typed in. Its own small part so the
// rest of the page can show before the address is read.
async function KeepView({ searchParams }: { searchParams: SearchParams }) {
  const view = parseView((await searchParams).view);
  return view === "baseline" ? <input type="hidden" name="view" value="baseline" /> : null;
}

export default function Home({ searchParams }: { searchParams: SearchParams }) {
  // The disclaimer is in layout.tsx, so every tab shows it.
  return (
    <main className="flex-1 p-4 sm:p-8 max-w-5xl w-full mx-auto">
      <h1 className="text-3xl font-semibold">Handover</h1>
      {/* T68 item 1: one-line pitch, so the first screen says what this is. */}
      <p className="mt-1 text-lg text-zinc-800">
        One patient record merged from three hospitals, with the source of every fact.
      </p>

      {/* A plain GET form: submitting it puts the ID in the address. */}
      <form action="/" method="get" className="mt-4">
        <label htmlFor="id" className="block font-medium">
          Patient ID
        </label>
        <div className="mt-1 flex gap-2">
          <input
            id="id"
            name="id"
            type="text"
            placeholder="D001"
            autoComplete="off"
            className="border border-zinc-500 rounded px-3 py-2 w-48"
          />
          <button type="submit" className="border border-zinc-800 bg-zinc-800 text-white rounded px-4 py-2">
            Show record
          </button>
        </div>
        <Suspense fallback={null}>
          <KeepView searchParams={searchParams} />
        </Suspense>
        <SampleIds />
      </form>

      <Suspense fallback={<p className="mt-6">Loading…</p>}>
        <Record searchParams={searchParams} />
      </Suspense>
    </main>
  );
}
