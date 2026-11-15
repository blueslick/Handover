// "Compare" view (T68 item 21): the Handover record on the left and the baseline on
// the right, section by section, so the same kind of fact sits side by side.
// On a narrow screen each section stacks: Handover first, then the baseline, each labelled.
import { splitSections } from "@/lib/sections";
import type { CompiledRecord } from "@/lib/types";
import FactList from "./FactList";
import BaselineSummary from "./BaselineSummary";
import WarningBanner from "./WarningBanner";

function SideLabel({ which }: { which: "handover" | "baseline" }) {
  return (
    <p className="font-medium text-quiet md:sr-only">
      {which === "handover" ? "Handover (our tool):" : "Baseline (keyword search):"}
    </p>
  );
}

function Empty() {
  return <p className="rounded-box border border-dashed border-line-strong p-3 text-quiet">None listed.</p>;
}

export default function CompareView({ handover, baseline }: { handover: CompiledRecord; baseline: CompiledRecord }) {
  const h = splitSections(handover.facts, "handover");
  const b = splitSections(baseline.facts, "baseline");
  // Keep a section if either side has something in it.
  const rows = h.sections
    .map((s, i) => ({ title: s.title, left: s.facts, right: b.sections[i].facts }))
    .filter((r) => r.left.length > 0 || r.right.length > 0);

  return (
    <div>
      {/* Column headings, on wide screens only (narrow screens label each cell instead). */}
      <div className="hidden md:grid md:grid-cols-2 gap-4 border-b border-line-strong py-2">
        <p className="text-base font-semibold">Handover (our tool): {handover.facts.length} facts</p>
        <p className="text-base font-semibold">Baseline (keyword search): {baseline.facts.length} entries</p>
      </div>

      <div className="mt-4 grid md:grid-cols-2 gap-4">
        <div>
          <SideLabel which="handover" />
          <WarningBanner facts={handover.facts} />
        </div>
        <div>
          <SideLabel which="baseline" />
          <p className="rounded-box border border-dashed border-line-strong p-3">
            The baseline gives no warnings: it has no checks, no conflict rule and no stop rule.
          </p>
          <div className="mt-4">
            <BaselineSummary handover={handover} baseline={baseline} />
          </div>
        </div>
      </div>

      {rows.map((r) => (
        <section key={r.title} className="mt-6">
          <h3 className="mb-2 text-base font-semibold">{r.title}</h3>
          <div className="grid md:grid-cols-2 gap-4 items-start">
            <div className="flex flex-col gap-2 min-w-0">
              <SideLabel which="handover" />
              {r.left.length > 0 ? <FactList facts={r.left} /> : <Empty />}
            </div>
            <div className="flex flex-col gap-2 min-w-0">
              <SideLabel which="baseline" />
              {r.right.length > 0 ? <FactList facts={r.right} idPrefix="baseline-" foldQuotes /> : <Empty />}
            </div>
          </div>
        </section>
      ))}
    </div>
  );
}
