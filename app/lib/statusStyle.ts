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
  const edge = conflict ? "border-2 border-alert" : "border border-sage";

  // A recorded allergy: the strongest colour (white on the app's one warning colour, orange; T75).
  if (fact.type === "allergy" && fact.status === "current") {
    return { card: `${edge} border-l-8 border-l-alert bg-white`, pill: "bg-alert text-white border border-alert", struck: false };
  }
  // A suspected allergy: orange outline, lighter fill.
  if (fact.type === "allergy" && fact.status === "suspected") {
    return { card: `${edge} border-l-8 border-l-alert bg-white`, pill: "bg-peach text-alert-ink border-2 border-alert", struck: false };
  }
  // A stopped medicine: grey, with the name struck through.
  if (fact.type === "medicine" && fact.status === "stopped") {
    return { card: `${edge} bg-mint`, pill: "bg-sage text-ink border border-soft", struck: true };
  }
  // Everything else (current, none recorded, planned...): plain.
  return { card: `${edge} bg-white`, pill: "bg-white text-ink border border-soft", struck: false };
}
