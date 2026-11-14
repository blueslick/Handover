// Loads one patient's compiled record from app/data/. The app never calls a model.
import { readFile } from "node:fs/promises";
import path from "node:path";
import type { CompiledRecord } from "./types";

// Patient IDs that have a file in app/data/. Add an ID here when its file is added.
export const SAMPLE_IDS = ["D001"];

// Returns the record, or null when the ID is unknown or the file is missing.
export async function loadRecord(rawId: string): Promise<CompiledRecord | null> {
  const id = rawId.trim().toUpperCase();
  // Only plain IDs such as D001 or P014 are accepted, so no one can ask for another path.
  if (!/^[A-Z]\d{3}$/.test(id) || !SAMPLE_IDS.includes(id)) return null;
  try {
    const file = path.join(process.cwd(), "data", `${id}_compiled.json`);
    return JSON.parse(await readFile(file, { encoding: "utf-8" })) as CompiledRecord;
  } catch {
    return null;
  }
}
