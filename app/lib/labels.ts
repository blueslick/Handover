// Words the app shows for each status and flag.
// Copied from display_labels in shared/fixed_lists.json (the app only reads app/data/,
// so it keeps its own copy; update both if the shared file changes).
import type { Fact, FactType, Flag, Status } from "./types";

export const STATUS_LABELS: Record<FactType, Partial<Record<Status, string>>> = {
  allergy: {
    current: "Allergy",
    suspected: "Suspected allergy",
    none_recorded: "No known allergies",
    side_effect: "Side effect, not an allergy",
  },
  medicine: {
    current: "Current",
    stopped: "Stopped",
    planned: "Planned",
    none_recorded: "No regular medicines recorded",
  },
  diagnosis: {
    current: "Current",
    stopped: "Resolved",
    suspected: "Suspected",
    family_history: "Family history",
  },
  operation: { current: "Done", planned: "Planned" },
};

export const FLAG_LABELS: Record<Flag, string> = {
  unverified: "Not verified against the source",
  conflict: "Hospitals disagree",
  missing_dose: "Dose not recorded",
  possible_missed: "Possibly missed",
  dose_changed: "Dose changed",
  unknown_name: "Unknown drug name",
};

export const FREQUENCY_LABELS: Record<string, string> = {
  once: "once",
  daily: "once a day",
  twice_daily: "twice a day",
  three_times_daily: "three times a day",
  four_times_daily: "four times a day",
  at_night: "at night",
  weekly: "weekly",
  as_needed: "as needed",
  other: "other",
};

// Falls back to the raw value so an unexpected status is still shown as a word.
export function statusLabel(fact: Pick<Fact, "type" | "status">): string {
  return STATUS_LABELS[fact.type]?.[fact.status] ?? fact.status;
}
