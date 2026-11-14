// Types for one compiled record, copied from shared/record_format.md.

export type FactType = "allergy" | "medicine" | "diagnosis" | "operation";
export type Status =
  | "current"
  | "stopped"
  | "none_recorded"
  | "suspected"
  | "family_history"
  | "planned"
  | "side_effect";
export type Flag =
  | "unverified"
  | "conflict"
  | "missing_dose"
  | "possible_missed"
  | "dose_changed"
  | "unknown_name";

// One place a fact was read from.
export interface Source {
  hospital: string;
  date: string;
  quote: string;
  file: string;
}

// An earlier, different value of the same fact.
export interface HistoryEntry {
  status: Status;
  dose: string | null;
  frequency: string | null;
  hospital: string;
  date: string;
  quote: string;
}

export interface Fact {
  fact_id: string;
  patient_id: string;
  type: FactType;
  name: string | null;
  name_as_written: string | null;
  dose: string | null;
  frequency: string | null;
  reaction: string | null;
  status: Status;
  hospital: string;
  date: string;
  quote: string;
  sources: Source[];
  history: HistoryEntry[];
  flags: Flag[];
  conflict_group: string | null;
}

export interface CompiledRecord {
  format_version: string;
  kind: string;
  patient_id: string;
  run_id: string | null;
  built_from: string[];
  facts: Fact[];
}
