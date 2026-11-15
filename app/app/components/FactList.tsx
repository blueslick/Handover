// Shows a list of facts. Facts that share a conflict_group go in one box, side by side,
// so neither side is hidden or ranked first.
import type { Fact } from "@/lib/types";
import FactCard from "./FactCard";
import { conflictAnchor } from "@/lib/banner";

// idPrefix keeps page ids unique when two records share a page (Compare view, T68 item 21).
export default function FactList({ facts, idPrefix = "" }: { facts: Fact[]; idPrefix?: string }) {
  // Walk the facts in order; the first fact of a group pulls in the rest of its group.
  const seenGroups = new Set<string>();
  const blocks: React.ReactNode[] = [];

  for (const fact of facts) {
    if (fact.conflict_group) {
      if (seenGroups.has(fact.conflict_group)) continue;
      seenGroups.add(fact.conflict_group);
      const group = facts.filter((f) => f.conflict_group === fact.conflict_group);
      blocks.push(
        <section
          key={fact.conflict_group}
          id={idPrefix + conflictAnchor(fact.conflict_group)}
          aria-label={`Hospitals disagree (${fact.conflict_group})`}
          className="scroll-mt-4 border-2 border-dashed border-amber-700 rounded p-3"
        >
          <p className="mb-2 text-sm font-semibold">
            Hospitals disagree. Both versions are shown:
          </p>
          <div className="flex flex-col md:flex-row gap-3">
            {group.map((f) => (
              <FactCard key={f.fact_id} fact={f} idPrefix={idPrefix} />
            ))}
          </div>
        </section>,
      );
    } else {
      blocks.push(<FactCard key={fact.fact_id} fact={fact} idPrefix={idPrefix} />);
    }
  }

  return <div className="flex flex-col gap-3">{blocks}</div>;
}
