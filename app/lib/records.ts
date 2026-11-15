// Loads one patient's compiled record from app/data/. The app never calls a model.
import { readFileSync } from "node:fs";
import { readFile } from "node:fs/promises";
import path from "node:path";
import type { CompiledRecord } from "./types";

import publishedIndex from "../data/index.json";

// Patient IDs the app may show: read from app/data/index.json, which
// scripts/sync-data.mjs copies from outputs/published/ (T34). Not typed in by hand.
export const SAMPLE_IDS: string[] = publishedIndex.patients.map((p) => p.patient_id);

// Live runs (T58): records made on Daniel's laptop by pipeline/tool/live_run.py.
// They live in app/data/live/, which is git-ignored, so they never reach GitHub or the
// public Vercel link. There the folder does not exist and this list is always empty.
export interface LiveRun {
  patient_id: string;
  run_id: string;
  model: string;
  made_at: string;
  tool: string;
  source_files: string[];
  records_used: string[];
  facts: number;
  conflicts: number;
}

// Read at the moment the page is shown (not when the app starts), so a new live run
// appears without restarting the app. Only IDs D901-D999 are accepted.
export function liveRuns(): LiveRun[] {
  try {
    const text = readFileSync(path.join(process.cwd(), "data", "live", "index.json"), "utf-8");
    const index = JSON.parse(text);
    if (!Array.isArray(index?.patients)) return [];
    return index.patients.filter(
      (p: LiveRun) => typeof p?.patient_id === "string" && /^D9\d\d$/.test(p.patient_id),
    );
  } catch {
    return [];
  }
}

export function liveRun(rawId: string): LiveRun | undefined {
  const id = rawId.trim().toUpperCase();
  return liveRuns().find((p) => p.patient_id === id);
}

// A patient the app knows: published (D001) or a live run on this laptop.
export function isKnownId(rawId: string): boolean {
  const id = rawId.trim().toUpperCase();
  return SAMPLE_IDS.includes(id) || liveRun(id) !== undefined;
}

// Which record to show (T27): the tool's merged record, or the keyword baseline
// for the same patient. File names in app/data/: <ID>_compiled.json and
// <ID>_baseline_keyword.json.
export type View = "handover" | "baseline";

const FILE_SUFFIX: Record<View, string> = {
  handover: "compiled",
  baseline: "baseline_keyword",
};

// What the doctor screen shows: one of the two records, or both side by side (T68 item 21).
export type PageView = View | "compare";

export function parsePageView(raw: string | string[] | undefined): PageView {
  const v = Array.isArray(raw) ? raw[0] : raw;
  return v === "compare" ? "compare" : parseView(v);
}

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
  if (!/^[A-Z]\d{3}$/.test(id)) return { state: "missing" };
  // Published patients are in app/data/; live runs (handover view only) in app/data/live/.
  let folder: string;
  if (SAMPLE_IDS.includes(id)) folder = "data";
  else if (view === "handover" && liveRun(id)) folder = path.join("data", "live");
  else return { state: "missing" };

  // A listed ID whose file can't be read is missing; one that can't be parsed is failed.
  let text: string;
  try {
    const file = path.join(process.cwd(), folder, `${id}_${FILE_SUFFIX[view]}.json`);
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
