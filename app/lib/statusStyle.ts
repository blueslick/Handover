// Colours for a card's status (T68 item 13). Colour is only added on top: the status is
// always also written in words, so nothing depends on seeing the colour (CLAUDE.md).
// Text and background pairs are dark-on-light or white-on-dark, all well above the
// 4.5:1 contrast needed for normal text.
import type { Fact } from "./types";

export interface StatusStyle {
  card: string; // extra classes for the card
  pill: string; // classes for the status label
  struck: boolean; // strike the name through (stopped medicines)
}

export function statusStyle(fact: Pick<Fact, "type" | "status" | "flags">): StatusStyle {
  const conflict = fact.flags.includes("conflict");
  // A disagreement between hospitals: amber edge on the card.
  const edge = conflict ? "border-2 border-amber-700" : "border border-zinc-400";

  // A recorded allergy: the strongest colour (white on dark red).
  if (fact.type === "allergy" && fact.status === "current") {
    return { card: `${edge} border-l-8 border-l-red-800 bg-white`, pill: "bg-red-800 text-white border border-red-800", struck: false };
  }
  // A suspected allergy: dark red outline, lighter fill.
  if (fact.type === "allergy" && fact.status === "suspected") {
    return { card: `${edge} border-l-8 border-l-red-800 bg-white`, pill: "bg-red-50 text-red-900 border-2 border-red-800", struck: false };
  }
  // A stopped medicine: grey, with the name struck through.
  if (fact.type === "medicine" && fact.status === "stopped") {
    return { card: `${edge} bg-zinc-100`, pill: "bg-zinc-300 text-zinc-900 border border-zinc-500", struck: true };
  }
  // Everything else (current, none recorded, planned...): plain.
  return { card: `${edge} bg-white`, pill: "bg-white text-zinc-900 border border-zinc-700", struck: false };
}
