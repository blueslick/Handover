// Doctor screen. The patient ID comes from the address (/?id=D001).
// Reads JSON from app/data/ only: no model calls, no key.
import Link from "next/link";
import { Suspense } from "react";
import { loadRecordState, SAMPLE_IDS } from "@/lib/records";
import type { Fact } from "@/lib/types";
import FactList from "./components/FactList";
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
function SampleIds() {
  return (
    <p className="mt-2 text-sm">
      Sample IDs:{" "}
      {SAMPLE_IDS.map((id) => (
        <Link key={id} href={`/?id=${id}`} className="underline font-medium mr-2">
          {id}
        </Link>
      ))}
    </p>
  );
}

// Looks up the ID and shows the record, a prompt (no ID yet) or the unknown-ID message.
async function Record({ searchParams }: { searchParams: Promise<{ id?: string | string[] }> }) {
  const { id: rawId } = await searchParams;
  const id = (Array.isArray(rawId) ? rawId[0] : rawId)?.trim() ?? "";

  if (!id) {
    return <p className="mt-6">Enter a patient ID above to see the merged record.</p>;
  }

  const load = await loadRecordState(id);

  // Failed state: the patient is listed but the file could not be read.
  if (load.state === "failed") {
    return (
      <div role="alert" className="mt-6 border-4 border-amber-700 bg-amber-50 text-amber-950 rounded p-4">
        <p className="font-bold">The record for “{id}” could not be loaded.</p>
        <p className="mt-1">The file is damaged, so nothing is shown rather than part of the record.</p>
      </div>
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
  const meds = ofType("medicine");

  return (
    <div className="mt-6">
      <h2 className="text-2xl font-semibold">Patient {record.patient_id}</h2>
      <p className="text-sm text-zinc-700">Merged from {record.built_from.length} hospital records.</p>
      <div className="mt-4">
        <WarningBanner facts={facts} />
      </div>
      <Section title="Allergies" facts={ofType("allergy")} />
      <Section title="Current medicines" facts={meds.filter((f) => f.status === "current")} />
      <Section title="Other medicines (stopped or planned)" facts={meds.filter((f) => f.status !== "current")} />
      <Section title="Diagnoses" facts={ofType("diagnosis")} />
      <Section title="Operations" facts={ofType("operation")} />
    </div>
  );
}

export default function Home({ searchParams }: { searchParams: Promise<{ id?: string | string[] }> }) {
  // The disclaimer is in layout.tsx, so every tab shows it.
  return (
    <main className="flex-1 p-4 sm:p-8 max-w-5xl w-full mx-auto">
      <h1 className="text-3xl font-semibold">Handover</h1>

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
        <SampleIds />
      </form>

      <Suspense fallback={<p className="mt-6">Loading…</p>}>
        <Record searchParams={searchParams} />
      </Suspense>
    </main>
  );
}
