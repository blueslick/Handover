// Splits a record's facts into the doctor screen's sections, in the order shown
// (T68 item 21: one place, so the single view and the side-by-side view line up).
import { isOlderNoMedicinesLine } from "./olderRecord";
import type { Fact } from "./types";

export interface RecordSection {
  title: string;
  facts: Fact[];
}

export function splitSections(facts: Fact[], view: "handover" | "baseline"): { sections: RecordSection[]; olderMeds: Fact[] } {
  const ofType = (t: Fact["type"]) => facts.filter((f) => f.type === t);
  // T67: in the Handover view, an older "no regular medicines" line moves to a greyed
  // history box when a later record lists current medicines. The baseline view lists
  // every line as found, so it is left alone.
  const olderMeds = view === "handover" ? ofType("medicine").filter((f) => isOlderNoMedicinesLine(f, facts)) : [];
  const meds = ofType("medicine").filter((f) => !olderMeds.includes(f));
  const sections: RecordSection[] = [
    { title: "Allergies", facts: ofType("allergy") },
    { title: "Current medicines", facts: meds.filter((f) => f.status === "current") },
    // T68 item 19: stopped medicines straight under current ones, with a plain warning heading.
    { title: "Stopped medicines: do not continue without checking", facts: meds.filter((f) => f.status === "stopped") },
    {
      title: "Other medicines (planned, or none recorded)",
      facts: meds.filter((f) => f.status !== "current" && f.status !== "stopped"),
    },
    { title: "Diagnoses", facts: ofType("diagnosis") },
    { title: "Operations", facts: ofType("operation") },
  ];
  return { sections, olderMeds };
}
