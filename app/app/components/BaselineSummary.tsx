// Short summary above the baseline of how it differs from Handover for this patient
// (T68 item 22). The lines come from lib/compare.ts, worked out from both records.
import { baselineDifferences } from "@/lib/compare";
import type { CompiledRecord } from "@/lib/types";

export default function BaselineSummary({ handover, baseline }: { handover: CompiledRecord; baseline: CompiledRecord }) {
  const lines = baselineDifferences(handover, baseline);
  return (
    <section aria-labelledby="baseline-diff" className="mt-4 border-2 border-zinc-800 rounded p-4 bg-white">
      <h2 id="baseline-diff" className="font-bold">How the baseline differs from Handover for this patient</h2>
      {lines.length === 0 ? (
        <p className="mt-1">For this patient, the baseline lists the same allergies and medicines as Handover.</p>
      ) : (
        <ul className="mt-2 list-disc pl-5 flex flex-col gap-1">
          {lines.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
