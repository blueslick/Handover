// Loads the results table for the "How we tested" tab from app/data/results.json.
// The app never calls a model; T39 swaps this file for the real numbers.
import { readFile } from "node:fs/promises";
import path from "node:path";

// One row of the build-up table. A null count means "not run yet".
export interface ResultRow {
  row: number;
  method: string;
  uses_ai: boolean;
  key_facts: number | null;
  missed: number | null;
  false_alarms: number | null;
  wrong_status: number | null;
  conflicts_shown: number | null;
  // How many conflicts the answer keys hold, so the tab can say "38 of 38". Optional,
  // so an older results file without it still loads.
  conflicts_total?: number | null;
}

// What the AI calls cost per patient (three hospital records) for one model, in US cents.
// A null means "not run yet". Filled from the held-out runs' token totals (T36, T62).
export interface CostEntry {
  model: string;
  us_cents: number | null;
}

// One worked failure example (filled in from T38).
export interface FailureExample {
  title: string;
  explanation: string;
}

// One age band and sex group: the full tool (row 7) next to the keyword baseline (row 1),
// all facts. Filled by scripts/make-results.mjs from outputs/results/heldout/by_age_sex.csv.
export interface AgeSexRow {
  age_band: string;
  sex: string;
  patients: number | null;
  key_facts: number | null;
  tool_missed: number | null;
  tool_false_alarms: number | null;
  baseline_missed: number | null;
  baseline_false_alarms: number | null;
}

// One kind of planted trap (T78): how many of the scored traps the full tool (row 7) and the
// keyword baseline (row 1) caught. Filled by scripts/make-results.mjs from traps_by_type.csv.
export interface TrapRow {
  kind: string;
  label: string;
  scored: number;
  tool_caught: number;
  baseline_caught: number;
}

export interface Results {
  status: "placeholder" | "final";
  updated: string | null;
  patients: number | null;
  note: string | null;
  rows: ResultRow[];
  omission_check: string | null;
  failure_examples: FailureExample[];
  // Optional, so an older results file without it still loads.
  cost_per_patient?: CostEntry[];
  // Optional (T71). Missing = the tab says "Not run yet".
  by_age_sex?: AgeSexRow[];
  // Optional (T78). Missing = the traps chart says "Not run yet".
  traps?: TrapRow[];
}

// Three outcomes, so the tab can tell "nothing yet" apart from "broken file".
export type ResultsLoad =
  | { state: "ok"; results: Results }
  | { state: "empty" }
  | { state: "failed"; reason: string };

// Checks the file has the shape the tab expects, so a bad edit shows the failed state
// instead of crashing the page.
function looksLikeResults(data: unknown): data is Results {
  if (!data || typeof data !== "object") return false;
  const d = data as Record<string, unknown>;
  if (d.status !== "placeholder" && d.status !== "final") return false;
  if (!Array.isArray(d.rows)) return false;
  if (!Array.isArray(d.failure_examples)) return false;
  if (d.cost_per_patient !== undefined && !Array.isArray(d.cost_per_patient)) return false;
  if (d.by_age_sex !== undefined && !Array.isArray(d.by_age_sex)) return false;
  if (d.traps !== undefined && !Array.isArray(d.traps)) return false;
  return d.rows.every(
    (r) => r && typeof r === "object" && typeof (r as ResultRow).method === "string",
  );
}

export async function loadResults(): Promise<ResultsLoad> {
  const file = path.join(process.cwd(), "data", "results.json");

  // No file at all = empty state.
  let text: string;
  try {
    text = await readFile(file, { encoding: "utf-8" });
  } catch {
    return { state: "empty" };
  }

  // A file that is not valid JSON, or has the wrong shape = failed state.
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    return { state: "failed", reason: "The results file is not valid JSON." };
  }
  if (!looksLikeResults(data)) {
    return { state: "failed", reason: "The results file does not have the expected fields." };
  }

  // A file with no rows = empty state.
  if (data.rows.length === 0) return { state: "empty" };
  return { state: "ok", results: data };
}
