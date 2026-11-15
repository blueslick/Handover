// "Compare" view (T68 item 21): the Handover record on the left and the baseline on
// the right, section by section, so the same kind of fact sits side by side.
// On a narrow screen each section stacks: Handover first, then the baseline, each labelled.
import { splitSections } from "@/lib/sections";
import type { CompiledRecord } from "@/lib/types";
import FactList from "./FactList";
import WarningBanner from "./WarningBanner";

function SideLabel({ which }: { which: "handover" | "baseline" }) {
  return (
    <p className="text-sm font-semibold text-zinc-700 md:sr-only">
      {which === "handover" ? "Handover (our tool):" : "Baseline (keyword search):"}
    </p>
  );
}

function Empty() {
  return <p className="text-sm text-zinc-700 border border-dashed border-zinc-400 rounded p-3">None listed.</p>;
}

export default function CompareView({ handover, baseline }: { handover: CompiledRecord; baseline: CompiledRecord }) {
  const h = splitSections(handover.facts, "handover");
  const b = splitSections(baseline.facts, "baseline");
  // Keep a section if either side has something in it.
  const rows = h.sections
    .map((s, i) => ({ title: s.title, left: s.facts, right: b.sections[i].facts }))
    .filter((r) => r.left.length > 0 || r.right.length > 0);

  return (
    <div className="mt-6">
      {/* Column headings, on wide screens only (narrow screens label each cell instead). */}
      <div className="hidden md:grid md:grid-cols-2 gap-4 sticky top-0 bg-white py-2 z-10 border-b border-zinc-300">
        <p className="text-lg font-semibold">Handover (our tool): {handover.facts.length} facts</p>
        <p className="text-lg font-semibold">Baseline (keyword search): {baseline.facts.length} entries</p>
      </div>

      <div className="mt-4 grid md:grid-cols-2 gap-4">
        <div>
          <SideLabel which="handover" />
          <WarningBanner facts={handover.facts} />
        </div>
        <div>
          <SideLabel which="baseline" />
          <p className="border-2 border-dashed border-zinc-500 rounded p-4">
            The baseline gives no warnings: it has no checks, no conflict rule and no stop rule.
          </p>
        </div>
      </div>

      {rows.map((r) => (
        <section key={r.title} className="mt-8">
          <h3 className="text-xl font-semibold mb-2">{r.title}</h3>
          <div className="grid md:grid-cols-2 gap-4 items-start">
            <div className="flex flex-col gap-2 min-w-0">
              <SideLabel which="handover" />
              {r.left.length > 0 ? <FactList facts={r.left} /> : <Empty />}
            </div>
            <div className="flex flex-col gap-2 min-w-0">
              <SideLabel which="baseline" />
              {r.right.length > 0 ? <FactList facts={r.right} idPrefix="baseline-" /> : <Empty />}
            </div>
          </div>
        </section>
      ))}
    </div>
  );
}
