// Builds the data for the upload screen (T28): app/data/walkthrough_<ID>.json.
//
//   node scripts/make-walkthrough.mjs --patient D001 --run 20261114-v1-sonnet-5-5
//
// Run from app/. Reads, never writes, outside app/:
//   ../pipeline/data/demo/<ID>/<ID>_A.csv, _B.txt, _C.txt   the three hospital records
//   ../outputs/checked/<run>/<ID>_<H>.json                  what the tool read, after Check
//   ../outputs/extracted/<run>/<ID>_<H>.call.json           tokens and whether it was retried
// A hospital with no checked file is written as "not_run", so the screen says so
// instead of inventing anything. No model calls: this only copies saved files.
// Only the demo patient folder is read, so no held-out record can end up here.
import { readFileSync, writeFileSync, existsSync, readdirSync } from "node:fs";
import path from "node:path";

const args = process.argv.slice(2);
const arg = (name) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 ? args[i + 1] : undefined;
};
const patient = (arg("patient") ?? "").toUpperCase();
const run = arg("run");
if (!/^D\d{3}$/.test(patient) || !run || !/^[\w.-]+$/.test(run)) {
  console.error("Usage: node scripts/make-walkthrough.mjs --patient D001 --run <run_id> (demo patients only)");
  process.exit(1);
}

const root = path.resolve(process.cwd(), "..");
const recordDir = path.join(root, "pipeline", "data", "demo", patient);
const FORMATS = {
  A: { ext: "csv", format: "Table (CSV file)" },
  B: { ext: "txt", format: "Free-text letter" },
  C: { ext: "txt", format: "Brand-name medication sheet" },
};

const hospitals = Object.entries(FORMATS).map(([h, { ext, format }]) => {
  const file = `${patient}_${h}.${ext}`;
  const recordText = readFileSync(path.join(recordDir, file), "utf-8");
  const checkedPath = path.join(root, "outputs", "checked", run, `${patient}_${h}.json`);
  if (!existsSync(checkedPath)) {
    return { hospital: h, file, format, record_text: recordText, state: "not_run", facts: [] };
  }
  const checked = JSON.parse(readFileSync(checkedPath, "utf-8"));
  const extractedDir = path.join(root, "outputs", "extracted", run);
  const callPath = path.join(extractedDir, `${patient}_${h}.call.json`);
  const call = existsSync(callPath) ? JSON.parse(readFileSync(callPath, "utf-8")) : null;
  const retried = existsSync(extractedDir)
    ? readdirSync(extractedDir).some((f) => f.startsWith(`${patient}_${h}.attempt2`))
    : false;

  // Same shape as one fact in a compiled record, so the doctor screen's fact card can show it.
  const facts = checked.facts.map((f, i) => ({
    fact_id: `${patient}-${h}${String(i + 1).padStart(2, "0")}`,
    patient_id: patient,
    type: f.type,
    name: f.name,
    name_as_written: f.name_as_written,
    dose: f.dose,
    frequency: f.frequency,
    reaction: f.reaction,
    status: f.status,
    hospital: h,
    date: f.date,
    quote: f.quote,
    sources: [{ hospital: h, date: f.date, quote: f.quote, file }],
    history: [],
    flags: f.flags ?? [],
    conflict_group: null,
  }));

  return {
    hospital: h,
    file,
    format,
    record_text: recordText,
    state: "ready",
    model: checked.model ?? null,
    retried,
    tokens: call?.usage ?? checked.usage ?? null,
    facts,
  };
});

const out = { format_version: "1.0", patient_id: patient, run_id: run, hospitals };
const outPath = path.join(process.cwd(), "data", `walkthrough_${patient}.json`);
writeFileSync(outPath, JSON.stringify(out, null, 2) + "\n");
console.log(
  `Wrote ${path.relative(process.cwd(), outPath)}: ` +
    hospitals.map((h) => `${h.hospital} ${h.state === "ready" ? `${h.facts.length} facts` : "not run"}`).join(", "),
);
