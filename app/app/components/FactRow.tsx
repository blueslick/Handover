// The short detail line for a fact: dose and frequency, or the reaction for an allergy.
// (T81: the doctor screen's rows are table rows in app/page.tsx now; this helper is what
// the source panel, the "see both" view and the records replay still share.)
import { FREQUENCY_LABELS } from "@/lib/labels";
import type { Fact } from "@/lib/types";

export function factDetail(fact: Fact): string {
  const parts: string[] = [];
  if (fact.dose) parts.push(fact.dose);
  if (fact.frequency) parts.push(FREQUENCY_LABELS[fact.frequency] ?? fact.frequency);
  if (fact.reaction) parts.push(`reaction: ${fact.reaction}`);
  return parts.join(", ");
}
