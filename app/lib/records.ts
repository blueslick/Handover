// Loads one patient's compiled record from app/data/. The app never calls a model.
import { readFile } from "node:fs/promises";
import path from "node:path";
import type { CompiledRecord } from "./types";

import publishedIndex from "../data/index.json";

// Patient IDs the app may show: read from app/data/index.json, which
// scripts/sync-data.mjs copies from outputs/published/ (T34). Not typed in by hand.
export const SAMPLE_IDS: string[] = publishedIndex.patients.map((p) => p.patient_id);

// Which record to show (T27): the tool's merged record, or the keyword baseline
// for the same patient. File names in app/data/: <ID>_compiled.json and
// <ID>_baseline_keyword.json.
export type View = "handover" | "baseline";

const FILE_SUFFIX: Record<View, string> = {
  handover: "compiled",
  baseline: "baseline_keyword",
};

// Reads the view from the address (?view=baseline). Anything else means Handover.
export function parseView(raw: string | string[] | undefined): View {
  const v = Array.isArray(raw) ? raw[0] : raw;
  return v === "baseline" ? "baseline" : "handover";
}

// Three outcomes, so the doctor screen can tell "no such patient" apart from
// "the file is there but damaged" (T29 failed state).
export type RecordLoad =
  | { state: "ok"; record: CompiledRecord }
  | { state: "missing" }
  | { state: "failed" };

export async function loadRecordState(rawId: string, view: View = "handover"): Promise<RecordLoad> {
  const id = rawId.trim().toUpperCase();
  // Only plain IDs such as D001 or P014 are accepted, so no one can ask for another path.
  if (!/^[A-Z]\d{3}$/.test(id) || !SAMPLE_IDS.includes(id)) return { state: "missing" };

  // A listed ID whose file can't be read is missing; one that can't be parsed is failed.
  let text: string;
  try {
    const file = path.join(process.cwd(), "data", `${id}_${FILE_SUFFIX[view]}.json`);
    text = await readFile(file, { encoding: "utf-8" });
  } catch {
    return { state: "missing" };
  }
  try {
    const record = JSON.parse(text) as CompiledRecord;
    if (!record || !Array.isArray(record.facts) || !Array.isArray(record.built_from)) {
      return { state: "failed" };
    }
    return { state: "ok", record };
  } catch {
    return { state: "failed" };
  }
}

// Returns the record, or null when the ID is unknown or the file is missing or damaged.
// Kept so older code that calls loadRecord() still works.
export async function loadRecord(rawId: string): Promise<CompiledRecord | null> {
  const load = await loadRecordState(rawId);
  return load.state === "ok" ? load.record : null;
}
