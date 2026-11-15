// Builds app/data/results.json for the "How we tested" tab from the committed
// held-out totals (T39). Copies numbers, never types them by hand.
//
//   node scripts/make-results.mjs
//
// Run from app/. Reads, never writes, outside app/:
//   ../outputs/results/heldout/buildup_table.csv     rows 1-8, "all" scope (T37)
//   ../outputs/results/heldout/cost_per_patient.csv  US cents per patient (T37)
//   ../outputs/results/heldout/omission_line.csv     omission-check counts (T37)
//   ../outputs/results/heldout/by_age_sex.csv        rows 1 and 7 per age band and sex (T37, used by T71)
//   ../outputs/results/heldout/traps_by_type.csv     planted traps caught, rows 1 and 7 (T37, used by T78)
// Held-out numbers only: working-patient results are never used here.
// The failure examples already in data/results.json are kept as they are (T38: pasted from\n// docs/failure_examples.md, section A).
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
  `full tool's ${om.row7_all_misses} misses. ${om.row7_name_absent_type_diagnosis} of those ` +
  `${om.row7_all_misses} are not real tool mistakes: ${om.row7_name_absent_type_diagnosis} diagnosis names in our ` +
  `answer key have a double space, so the tool's correct answer was counted as missed (and as a false alarm). ` +
  `Most of the rest are combination medicines read as their two ingredients, which still look present by name, ` +
  `so the word search cannot spot them. It is a hint for the doctor, not a fact.`;

// Age and sex groups (T71): the full tool (row 7) next to the keyword baseline (row 1),
// all facts. Stops if the eight groups don't add up to the build-up table.
const ageSex = readCsv("by_age_sex.csv").filter((r) => r.scope === "all");
const groupKey = (r) => `${r.age_band}|${r.sex}`;
const toolGroups = ageSex.filter((r) => r.row === "7");
const baseGroups = new Map(ageSex.filter((r) => r.row === "1").map((r) => [groupKey(r), r]));
if (toolGroups.length !== 8 || baseGroups.size !== 8) {
  fail(`expected 8 age and sex groups for rows 1 and 7 in by_age_sex.csv, found ${toolGroups.length} and ${baseGroups.size}`);
}
const by_age_sex = toolGroups.map((t) => {
  const b = baseGroups.get(groupKey(t));
  if (!b) fail(`row 1 has no group ${t.age_band} ${t.sex}`);
  if (b.patients !== t.patients || b.key_facts !== t.key_facts) fail(`rows 1 and 7 disagree for ${t.age_band} ${t.sex}`);
  return {
    age_band: t.age_band,
    sex: t.sex,
    patients: int(t.patients, "patients"),
    key_facts: int(t.key_facts, "key_facts"),
    tool_missed: int(t.missed, "missed"),
    tool_false_alarms: int(t.false_alarms, "false_alarms"),
    baseline_missed: int(b.missed, "missed"),
    baseline_false_alarms: int(b.false_alarms, "false_alarms"),
  };
});
const sum = (k) => by_age_sex.reduce((a, g) => a + g[k], 0);
const row1 = rows.find((r) => r.row === 1);
const checks = [
  ["patients", sum("patients"), int([...patients][0], "patients")],
  ["key facts", sum("key_facts"), row7.key_facts],
  ["full tool missed", sum("tool_missed"), row7.missed],
  ["full tool false alarms", sum("tool_false_alarms"), row7.false_alarms],
  ["baseline missed", sum("baseline_missed"), row1.missed],
  ["baseline false alarms", sum("baseline_false_alarms"), row1.false_alarms],
];
for (const [what, got, want] of checks) {
  if (got !== want) fail(`age and sex groups add up to ${got} ${what}, but the build-up table says ${want}`);
}

// Planted traps (T78): for each kind of trap, how many the full tool (row 7) and the keyword
// baseline (row 1) caught, out of the traps that could be scored (traps whose label was
// overtaken by a later record are left out, as in T37). Stops if the kinds don't add up.
const TRAP_WORDS = {
  stop_one_hospital: "Medicine stopped at one hospital only",
  dose_change: "Dose changed between hospitals",
  silent_medicine: "Latest hospital leaves out a medicine",
  allergy_missed: "One hospital leaves out an allergy",
};
const trapCsv = readCsv("traps_by_type.csv");
const trapLine = (kind, row) => {
  const r = trapCsv.find((t) => t.trap_type === kind && t.row === String(row));
  if (!r) fail(`traps_by_type.csv has no line for ${kind}, row ${row}`);
  return { caught: int(r.caught, "caught"), scored: int(r.caught, "caught") + int(r.not_caught, "not_caught") };
};
const traps = Object.entries(TRAP_WORDS).map(([kind, label]) => {
  const t = trapLine(kind, 7);
  const b = trapLine(kind, 1);
  if (t.scored !== b.scored) fail(`rows 1 and 7 score a different number of ${kind} traps`);
  return { kind, label, scored: t.scored, tool_caught: t.caught, baseline_caught: b.caught };
});
const kinds = new Set(trapCsv.filter((t) => t.trap_type !== "all").map((t) => t.trap_type));
if (kinds.size !== traps.length) fail(`traps_by_type.csv has ${kinds.size} kinds of trap, the app knows ${traps.length}`);
for (const row of [1, 7]) {
  const all = trapLine("all", row);
  const got = traps.reduce((a, t) => a + (row === 7 ? t.tool_caught : t.baseline_caught), 0);
  const scored = traps.reduce((a, t) => a + t.scored, 0);
  if (got !== all.caught || scored !== all.scored) fail(`trap kinds don't add up to the 'all' line for row ${row}`);
}

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
  by_age_sex,
  traps,
};

writeFileSync(outFile, JSON.stringify(results, null, 2) + "\n");
console.log(
  `make-results: wrote data/results.json: ${rows.length} rows, ${results.patients} patients, ` +
    `${by_age_sex.length} age and sex groups, ${traps.length} kinds of trap, ${failure_examples.length} failure examples`,
);
