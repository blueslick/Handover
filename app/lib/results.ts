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
}

// One worked failure example (filled in from T38).
export interface FailureExample {
  title: string;
  explanation: string;
}

export interface Results {
  status: "placeholder" | "final";
  updated: string | null;
  patients: number | null;
  note: string | null;
  rows: ResultRow[];
  omission_check: string | null;
  failure_examples: FailureExample[];
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
