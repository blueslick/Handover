// Loads the saved run the upload screen replays (T28): app/data/walkthrough_<ID>.json,
// made by scripts/make-walkthrough.mjs. The app never calls a model.
import { readFile } from "node:fs/promises";
import path from "node:path";
import type { Fact } from "./types";

export interface WalkthroughHospital {
  hospital: string;
  file: string;
  format: string;
  record_text: string;
  // "ready" = the tool's saved reading exists; "not_run" = not run on this record yet.
  state: "ready" | "not_run";
  model?: string | null;
  retried?: boolean;
  tokens?: { input_tokens: number; output_tokens: number } | null;
  facts: Fact[];
}

export interface Walkthrough {
  format_version: string;
  patient_id: string;
  run_id: string;
  hospitals: WalkthroughHospital[];
}

// The patient the upload screen replays.
export const WALKTHROUGH_ID = "D001";

export type WalkthroughLoad =
  | { state: "ok"; walkthrough: Walkthrough }
  | { state: "missing" }
  | { state: "failed" };

export async function loadWalkthrough(id: string = WALKTHROUGH_ID): Promise<WalkthroughLoad> {
  let text: string;
  try {
    text = await readFile(path.join(process.cwd(), "data", `walkthrough_${id}.json`), "utf-8");
  } catch {
    return { state: "missing" };
  }
  try {
    const w = JSON.parse(text) as Walkthrough;
    const ok =
      w &&
      Array.isArray(w.hospitals) &&
      w.hospitals.every((h) => typeof h.record_text === "string" && Array.isArray(h.facts));
    return ok ? { state: "ok", walkthrough: w } : { state: "failed" };
  } catch {
    return { state: "failed" };
  }
}
