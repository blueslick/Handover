// How a full fact card looks for each status (baseline and compare views; T81 colours).
// Colour is only added on top: the status is always also written in words, so nothing
// depends on seeing the colour (CLAUDE.md).
import type { Fact } from "./types";

export interface StatusStyle {
  card: string; // extra classes for the card
  // "crit" puts the status in a red label (a recorded or suspected allergy); otherwise plain text.
  label: "crit" | "plain";
}

export function statusStyle(fact: Pick<Fact, "type" | "status" | "flags">): StatusStyle {
  // A disagreement between hospitals: amber edge on the card.
  const edge = fact.flags.includes("conflict") ? "border-warn-line" : "border-line";
  const allergy = fact.type === "allergy" && (fact.status === "current" || fact.status === "suspected");
  return { card: `border ${edge} bg-surface`, label: allergy ? "crit" : "plain" };
}
