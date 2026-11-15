// T67 (from Q09): an older "No regular medicines recorded" line from an early hospital
// can sit next to current medicines from a later hospital, which could confuse a doctor.
// Display only: the fact itself, the tool and every score are unchanged.
import type { Fact } from "./types";

// True when a medicine fact saying "none recorded" should move into the greyed
// older-record history. All of these must hold:
//   1. it is a medicine fact with status none_recorded (never an allergy: "no known
//      allergies" next to a real allergy is a conflict and stays side by side);
//   2. it is not part of a conflict (no conflict_group and no conflict flag);
//   3. the same patient has a current medicine from a LATER record.
// Dates are YYYY-MM-DD, so comparing the text compares the dates.
export function isOlderNoMedicinesLine(fact: Fact, facts: Fact[]): boolean {
  if (fact.type !== "medicine" || fact.status !== "none_recorded") return false;
  if (fact.conflict_group || fact.flags.includes("conflict")) return false;
  return facts.some(
    (f) => f.type === "medicine" && f.status === "current" && f.date > fact.date,
  );
}
