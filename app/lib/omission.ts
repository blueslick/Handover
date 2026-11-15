// Loads one patient's omission-check flags from app/data/<ID>_omission.json (T64).
// The file is the omission check's saved output (pipeline/eval/omission_check.py), joined per
// patient by `store.py publish --with-omission` and copied here by scripts/sync-data.mjs.
// It is a word-search hint, not a fact: the doctor screen shows it in its own box.
// The app never calls a model.
import { readFile } from "node:fs/promises";
import path from "node:path";

export interface OmissionLine {
  line: number;
  text: string;
}

export interface OmissionFlag {
  flag: string;
  generic: string;
  terms_as_written: string[];
  lines: OmissionLine[];
}

export interface OmissionRecord {
  hospital: string;
  source_file: string | null;
  flags: OmissionFlag[];
}

export interface OmissionFile {
  format_version: string;
  kind: "omission_check";
  patient_id: string;
  run_id: string;
  records: OmissionRecord[];
  not_checked: string[];
}

export type OmissionLoad =
  | { state: "ok"; omission: OmissionFile }
  | { state: "missing" }
  | { state: "failed" };

// `id` must already be a checked, listed patient ID (the doctor screen only calls this
// after the compiled record has loaded). `runId` is that record's run, so flags from a
// different run are never shown next to it.
export async function loadOmission(id: string, runId: string | null): Promise<OmissionLoad> {
  if (!/^[A-Z]\d{3}$/.test(id)) return { state: "missing" };
  let text: string;
  try {
    text = await readFile(path.join(process.cwd(), "data", `${id}_omission.json`), "utf-8");
  } catch {
    return { state: "missing" };
  }
  try {
    const o = JSON.parse(text) as OmissionFile;
    const ok =
      o &&
      o.kind === "omission_check" &&
      o.patient_id === id &&
      o.run_id === runId &&
      Array.isArray(o.records) &&
      o.records.every((r) => Array.isArray(r.flags));
    return ok ? { state: "ok", omission: o } : { state: "failed" };
  } catch {
    return { state: "failed" };
  }
}
