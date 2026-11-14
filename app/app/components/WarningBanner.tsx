// Banner at the top: shown when any allergy or medicine (the critical facts) has a flag.
import { FLAG_LABELS } from "@/lib/labels";
import type { Fact } from "@/lib/types";

// Short name for the banner list.
function label(f: Fact): string {
  return f.name ?? f.name_as_written ?? "No name recorded";
}

export default function WarningBanner({ facts }: { facts: Fact[] }) {
  const flagged = facts.filter(
    (f) => (f.type === "allergy" || f.type === "medicine") && f.flags.length > 0,
  );
  if (flagged.length === 0) return null;

  return (
    <div role="alert" className="border-4 border-amber-700 bg-amber-50 text-amber-950 rounded p-4">
      <h2 className="text-lg font-bold">Warning: check these before relying on this record</h2>
      <ul className="mt-2 list-disc pl-5">
        {flagged.map((f) => (
          <li key={f.fact_id}>
            {f.type === "allergy" ? "Allergy" : "Medicine"} “{label(f)}”:{" "}
            {f.flags.map((flag) => FLAG_LABELS[flag]).join(", ")}
          </li>
        ))}
      </ul>
    </div>
  );
}
