// Builds app/data/results.json for the "How we tested" tab from the committed
// held-out totals (T39). Copies numbers, never types them by hand.
//
//   node scripts/make-results.mjs
//
// Run from app/. Reads, never writes, outside app/:
//   ../outputs/results/heldout/buildup_table.csv     rows 1-8, "all" scope (T37)
//   ../outputs/results/heldout/cost_per_patient.csv  US cents per patient (T37)
//   ../outputs/results/heldout/omission_line.csv     omission-check counts (T37)
// Held-out numbers only: working-patient results are never used here.
// The failure examples already in data/results.json are kept as they are (T38 adds them).
// No model calls: this only reads CSV files.
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import path from "node:path";

const root = path.resolve(process.cwd(), "..");
const resultsDir = path.join(root, "outputs", "results", "heldout");
const outFile = path.join(process.cwd(), "data", "results.json");

const fail = (msg) => {
  console.error(`make-results: ${msg}`);
  process.exit(1);
};

// Small CSV reader: handles quoted fields with commas (the method names have them).
function readCsv(name) {
  const file = path.join(resultsDir, name);
  if (!existsSync(file)) fail(`missing ${file}`);
  const lines = readFileSync(file, "utf-8").trim().split(/\r?\n/);
  const split = (line) => {
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
  };
  const header = split(lines[0]);
  return lines.slice(1).map((line) => {
    const cells = split(line);
    return Object.fromEntries(header.map((h, i) => [h, cells[i]]));
  });
}

const int = (v, what) => {
  const n = Number(v);
  if (!Number.isInteger(n)) fail(`${what} is not a whole number: ${v}`);
  return n;
};

// Build-up table: one row per method, all facts (allergies, medicines, diagnoses, operations).
const table = readCsv("buildup_table.csv").filter((r) => r.scope === "all");
if (table.length !== 8) fail(`expected 8 'all' rows in buildup_table.csv, found ${table.length}`);
const patients = new Set(table.map((r) => r.patients));
if (patients.size !== 1) fail("rows disagree on the number of patients");

const rows = table
  .map((r) => ({
    row: int(r.row, "row"),
    method: r.name,
    uses_ai: int(r.row, "row") >= 4,
    key_facts: int(r.key_facts, "key_facts"),
    missed: int(r.missed, "missed"),
    false_alarms: int(r.false_alarms, "false_alarms"),
    wrong_status: int(r.wrong_status, "wrong_status"),
    conflicts_shown: int(r.conflict_shown, "conflict_shown"),
    conflicts_total: int(r.conflict_facts, "conflict_facts"),
  }))
  .sort((a, b) => a.row - b.row);

// Cost per patient (three hospital records), from the held-out runs' token totals.
const costRows = readCsv("cost_per_patient.csv");
const cents = (row) => {
  const r = costRows.find((c) => c.row === String(row));
  if (!r) fail(`no cost line for row ${row}`);
  return Math.round(Number(r.us_cents_per_patient) * 100) / 100;
};
const cost_per_patient = [
  { model: "Claude Sonnet 5.5 (the model the tool uses)", us_cents: cents(7) },
  { model: "Claude Haiku 5.5 (row 8)", us_cents: cents(8) },
];

// Omission check: one sentence under the table, numbers from the CSV.
const om = Object.fromEntries(readCsv("omission_line.csv").map((r) => [r.measure, int(r.count, r.measure)]));
const row7 = rows.find((r) => r.row === 7);
if (om.row7_all_misses !== row7.missed) fail("omission_line.csv and buildup_table.csv disagree on row 7 misses");
const omission_check =
  `A separate word search flagged ${om.possible_missed_flags} words as "possibly missed" across ` +
  `${om.records_checked} hospital records. It pointed at ${om.row7_all_misses_pointed_at_by_a_flag} of the ` +
  `full tool's ${om.row7_all_misses} misses: it only looks for medicine and allergy words, so it cannot see the ` +
  `${om.row7_name_absent_type_diagnosis} missed diagnoses, and the ${om.row7_name_absent_type_medicine} missed ` +
  `medicines (combination medicines read as their two ingredients) still look present by name. ` +
  `It is a hint for the doctor, not a fact.`;

// Keep any failure examples already in the file (T38 adds them).
let failure_examples = [];
if (existsSync(outFile)) {
  try {
    const old = JSON.parse(readFileSync(outFile, "utf-8"));
    if (Array.isArray(old.failure_examples)) failure_examples = old.failure_examples;
  } catch {
    fail("data/results.json exists but is not valid JSON; fix it before rerunning");
  }
}

const results = {
  status: "final",
  updated: "2026-11-15",
  patients: int([...patients][0], "patients"),
  note:
    "Held-out results only (160 patients, never used for tuning). Built by app/scripts/make-results.mjs " +
    "from outputs/results/heldout/ (T37, commit f48ef99). Missed includes wrong-status cases.",
  rows,
  cost_per_patient,
  omission_check,
  failure_examples,
};

writeFileSync(outFile, JSON.stringify(results, null, 2) + "\n");
console.log(
  `make-results: wrote data/results.json: ${rows.length} rows, ${results.patients} patients, ` +
    `${failure_examples.length} failure examples`,
);
