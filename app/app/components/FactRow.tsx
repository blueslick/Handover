// One line for one fact on the doctor screen (T75): the name, the dose, and its status in
// words. Tapping the line shows where the fact came from (its quotes and history) in the
// right-hand panel, so the list stays short and the source is one tap away.
import Link from "next/link";
import { FLAG_LABELS, FREQUENCY_LABELS, statusLabel } from "@/lib/labels";
import { doseChange, factAnchor } from "@/lib/banner";
import { formatDate } from "@/lib/dates";
import { factHospitals, factName } from "@/lib/names";
import type { Fact } from "@/lib/types";
import Tip from "./Tip";

// Dose and frequency, or the reaction for an allergy.
export function factDetail(fact: Fact): string {
  const parts: string[] = [];
  if (fact.dose) parts.push(fact.dose);
  if (fact.frequency) parts.push(FREQUENCY_LABELS[fact.frequency] ?? fact.frequency);
  if (fact.reaction) parts.push(`reaction: ${fact.reaction}`);
  return parts.join(", ");
}

// children: the fact's source, shown straight under the line on a phone or tablet, where
// the right-hand panel sits far below the list.
export default function FactRow({ fact, href, selected, showStatus = true, children }: { fact: Fact; href: string; selected: boolean; showStatus?: boolean; children?: React.ReactNode }) {
  const detail = factDetail(fact);
  const change = fact.flags.includes("dose_changed") ? doseChange(fact) : null;
  const otherFlags = fact.flags.filter((f) => f !== "conflict" && f !== "dose_changed");
  const hospitals = factHospitals(fact);
  return (
    <li id={factAnchor(fact.fact_id)} className="scroll-mt-4">
      <Link
        href={href}
        scroll={false}
        aria-current={selected ? "true" : undefined}
        className={`flex flex-wrap items-center gap-x-4 gap-y-1 rounded-2xl px-4 py-3 sm:grid sm:grid-cols-3 ${selected ? "bg-mint" : "hover:bg-mint/60"}`}
      >
        <span className={`flex-1 basis-40 text-lg font-medium break-words ${detail ? "" : "sm:col-span-2"}`}>{factName(fact)}</span>
        {detail && <span className="flex-1 basis-40">{detail}</span>}
        <span className="flex flex-wrap items-center gap-2 text-sm sm:justify-end">
          {/* The status, always as a word (CLAUDE.md). Hidden from sight only where the card's heading already says it. */}
          <span className={showStatus ? "text-soft" : "sr-only"}>{statusLabel(fact)}</span>
          {change && (
            <Tip tip={change.sameFreq ? `${change.from} to ${fact.dose}` : `${change.from} to ${change.to}`}>
              <span className="rounded-full border border-soft px-3 py-0.5 font-medium">{FLAG_LABELS.dose_changed}</span>
            </Tip>
          )}
          {!change && fact.flags.includes("dose_changed") && (
            <span className="rounded-full border border-soft px-3 py-0.5 font-medium">{FLAG_LABELS.dose_changed}</span>
          )}
          {otherFlags.map((f) => (
            <span key={f} className="rounded-full bg-peach text-alert-ink px-3 py-0.5 font-medium">
              {FLAG_LABELS[f]}
            </span>
          ))}
          <Tip
            tip={
              <>
                {fact.sources.map((s) => (
                  <span key={`${s.file}-${s.date}`} className="block">
                    Hospital {s.hospital}, {formatDate(s.date)}
                  </span>
                ))}
              </>
            }
          >
            <span className="text-soft">
              <span className="sr-only">From hospital{hospitals.length > 1 ? "s" : ""} </span>
              {hospitals.join(", ")}
            </span>
          </Tip>
        </span>
      </Link>
      {selected && children && <div className="mx-2 mt-2 mb-3 xl:hidden">{children}</div>}
    </li>
  );
}
