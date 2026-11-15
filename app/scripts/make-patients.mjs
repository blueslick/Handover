// T81: builds app/data/patients.json, the patient banner's name, date of birth and sex.
// The merged record has no such fields, so they are read from each patient's own Hospital A
// record (the table file), from its PatientName, DOB and Sex columns. Display only.
// Only the patients the app already shows (app/data/index.json) are read, and only from the
// demo and working folders. Held-out and reserve folders are never opened.
// Run from the app/ folder:  node scripts/make-patients.mjs
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import path from "node:path";

const root = path.resolve(process.cwd(), "..");
const dataDir = path.join(process.cwd(), "data");

const fail = (msg) => {
  console.error(`make-patients: ${msg}`);
  process.exit(1);
};

// Splits one line of a table file into its cells (handles "Last, First" in quotes).
function splitLine(line) {
  const out = [];
  let cur = "";
  let quoted = false;
  for (const ch of line) {
    if (ch === '"') quoted = !quoted;
    else if (ch === "," && !quoted) {
      out.push(cur);
      cur = "";
    } else cur += ch;
  }
  out.push(cur);
  return out;
}

const index = JSON.parse(readFileSync(path.join(dataDir, "index.json"), "utf-8"));
if (!Array.isArray(index.patients)) fail("app/data/index.json lists no patients");

const patients = {};
const skipped = [];
for (const p of index.patients) {
  const id = p.patient_id;
  if (!/^[A-Z]\d{3}$/.test(id)) fail(`bad patient ID in index: ${id}`);
  // Demo patients start with D, working patients with P. Nothing else is published.
  const folder = id.startsWith("D") ? "demo" : id.startsWith("P") ? "working" : null;
  if (!folder) fail(`${id} is neither a demo nor a working patient`);
  const file = path.join(root, "pipeline", "data", folder, id, `${id}_A.csv`);
  if (!existsSync(file)) {
    skipped.push(id);
    continue;
  }
  const [head, first] = readFileSync(file, "utf-8").split(/\r?\n/).filter((l) => l.trim() !== "").map(splitLine);
  if (!head || !first) fail(`${file} has no data row`);
  const cell = (name) => first[head.indexOf(name)] ?? "";
  if (cell("MRN") !== id) fail(`${file} is not ${id}'s record`);
  const [family, given] = cell("PatientName").split(",").map((s) => s.trim());
  const dob = cell("DOB");
  const sex = cell("Sex");
  if (!family || !given || !/^\d{4}-\d{2}-\d{2}$/.test(dob) || !["F", "M"].includes(sex)) fail(`${file}: name, date of birth or sex is missing or in an unexpected form`);
  patients[id] = { family, given, dob, sex };
}

writeFileSync(path.join(dataDir, "patients.json"), JSON.stringify({ note: "Built by app/scripts/make-patients.mjs from each patient's Hospital A record. Display only.", patients }, null, 2) + "\n");
console.log(`make-patients: wrote data/patients.json for ${Object.keys(patients).length} patient(s)` + (skipped.length ? `; no Hospital A record for ${skipped.join(", ")}` : ""));
