// Copies what the app shows from outputs/published/ into app/data/ (T34).
//
//   node scripts/sync-data.mjs
//
// Run from app/, after Daniel's `store.py publish`. Vercel builds from app/ only,
// so the copy is committed (shared/folders_and_names.md, "The app and its data").
// Reads, never writes, outside app/:
//   ../outputs/published/index.json                which patients the app may show
//   ../outputs/published/compiled/<ID>.json        the tool's merged record
//   ../outputs/published/baseline_keyword/<ID>.json  the keyword baseline, if has_baseline
//   ../outputs/published/omission/<ID>.json        omission-check flags, if omission_flags is a number (T64)
// Writes into app/data/:
//   index.json, <ID>_compiled.json, <ID>_baseline_keyword.json, <ID>_omission.json
// Any <ID>_compiled.json, <ID>_baseline_keyword.json or <ID>_omission.json in app/data/ that is not in
// the published index is removed, so no older record (or the hand-written sample)
// is left behind. walkthrough_*.json and results.json are left alone.
// No model calls: this only copies files.
import { readFileSync, writeFileSync, copyFileSync, existsSync, readdirSync, unlinkSync } from "node:fs";
import path from "node:path";

const root = path.resolve(process.cwd(), "..");
const pub = path.join(root, "outputs", "published");
const dataDir = path.join(process.cwd(), "data");

const fail = (msg) => {
  console.error(`sync-data: ${msg}`);
  process.exit(1);
};

const indexPath = path.join(pub, "index.json");
if (!existsSync(indexPath)) fail("outputs/published/index.json not found. Run store.py publish first.");
const index = JSON.parse(readFileSync(indexPath, "utf-8"));
if (!Array.isArray(index.patients) || index.patients.length === 0) fail("published index lists no patients.");

const keep = new Set(["index.json"]);
for (const p of index.patients) {
  const id = p.patient_id;
  if (!/^[A-Z]\d{3}$/.test(id)) fail(`bad patient ID in index: ${id}`);

  const compiled = path.join(pub, "compiled", `${id}.json`);
  if (!existsSync(compiled)) fail(`index lists ${id} but published/compiled/${id}.json is missing.`);
  const rec = JSON.parse(readFileSync(compiled, "utf-8"));
  if (rec.patient_id !== id || rec.kind !== "compiled") fail(`published/compiled/${id}.json is not ${id}'s compiled record.`);
  if (rec.run_id !== index.compiled_run_id) fail(`${id} is from run ${rec.run_id}, index says ${index.compiled_run_id}.`);
  copyFileSync(compiled, path.join(dataDir, `${id}_compiled.json`));
  keep.add(`${id}_compiled.json`);

  if (p.has_baseline) {
    const base = path.join(pub, "baseline_keyword", `${id}.json`);
    if (!existsSync(base)) fail(`index says ${id} has a baseline but the file is missing.`);
    copyFileSync(base, path.join(dataDir, `${id}_baseline_keyword.json`));
    keep.add(`${id}_baseline_keyword.json`);
  }

  if (typeof p.omission_flags === "number") {
    const om = path.join(pub, "omission", `${id}.json`);
    if (!existsSync(om)) fail(`index gives ${id} omission flags but published/omission/${id}.json is missing.`);
    const doc = JSON.parse(readFileSync(om, "utf-8"));
    if (doc.patient_id !== id || doc.kind !== "omission_check" || doc.run_id !== index.compiled_run_id)
      fail(`published/omission/${id}.json is not ${id}'s omission check for run ${index.compiled_run_id}.`);
    copyFileSync(om, path.join(dataDir, `${id}_omission.json`));
    keep.add(`${id}_omission.json`);
  }
}

const removed = [];
for (const f of readdirSync(dataDir)) {
  if (/^[A-Z]\d{3}_(compiled|baseline_keyword|omission)\.json$/.test(f) && !keep.has(f)) {
    unlinkSync(path.join(dataDir, f));
    removed.push(f);
  }
}
writeFileSync(path.join(dataDir, "index.json"), JSON.stringify(index, null, 2) + "\n");

console.log(
  `Synced run ${index.compiled_run_id}: ${index.patients.length} patient(s) ` +
    `(${index.patients.map((p) => p.patient_id).join(", ")})` +
    (removed.length ? `; removed ${removed.join(", ")}` : ""),
);
