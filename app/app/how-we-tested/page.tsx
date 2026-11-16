// "How we tested" tab: how the test was run, the results and the failure examples.
// Reads app/data/results.json only (see lib/results.ts), which scripts/make-results.mjs
// builds from the held-out results files. No number on this page is typed by hand.
// T81 (clinical look) and T82 (chart fixes): the dataset is stated once at the top, then
//   1. the headline chart: missed facts and false alarms, the full tool against the other
//      methods, with a switch to "allergies and medicines only" (where Microsoft Azure is);
//   2. the build chart: what each step of the tool adds, with false alarms split into
//      repeats and the rest;
//   3. tables: by age and sex, planted traps, and where the tool got it wrong.
// The baseline and side-by-side views for one patient, and the method, limits and cost,
// fold open at the bottom.
import { Suspense } from "react";
import { loadResults, type ResultRow, type Results } from "@/lib/results";
import { SAMPLE_IDS } from "@/lib/records";
import Page, { Box, Card } from "../components/Page";
import { Axis, BarRow, fmt, niceMax, percent } from "./Bars";
import CostLine from "./CostLine";
import MethodChart, { type MethodLine, type MethodView } from "./MethodChart";

export const metadata = { title: "How we tested · Handover" };

// The team's write-up, where the longer Azure caveats live (the same link as the README).
const WRITE_UP = "https://docs.google.com/document/d/1lHzcvi0vvmdCBLFHJB3e1dCduw-LKhDw7dX_G8oRlHE/edit";

// A row with every number the charts need, or null while the results are placeholders.
type FullRow = ResultRow & { key_facts: number; missed: number; false_alarms: number; matched: number; output_facts: number; repeats: number };
function full(r?: ResultRow): FullRow | null {
  if (!r) return null;
  const need = [r.key_facts, r.missed, r.false_alarms, r.matched, r.output_facts, r.repeats];
  return need.every((v) => typeof v === "number") ? (r as FullRow) : null;
}

// The short names the charts use for the rows of the build-up table.
const BASELINE_NAMES: Record<number, string> = { 2: "medSpaCy", 1: "Keyword search", 3: "Keyword search with rules" };
const BUILD_STEPS: Record<number, string> = { 4: "1. Plain lists", 5: "2. + Status labels", 6: "3. + Check against source", 7: "4. + Merge rules (full tool)" };

// The two views of the headline chart, built from the results file.
function methodViews(results: Results): MethodView[] {
  const row = (n: number) => full(results.rows.find((r) => r.row === n));
  const tool = row(7);
  if (!tool) return [];
  const line = (label: string, isTool: boolean, r: { missed: number; false_alarms: number; matched: number; key_facts: number; output_facts: number }): MethodLine => ({
    label,
    tool: isTool,
    missed: r.missed,
    false_alarms: r.false_alarms,
    matched: r.matched,
    key_facts: r.key_facts,
    output_facts: r.output_facts,
  });
  const views: MethodView[] = [
    {
      key: "all",
      button: `All facts (${fmt(tool.key_facts)})`,
      others: "baseline",
      lines: [line("Full tool", true, tool), ...[2, 1, 3].flatMap((n) => (row(n) ? [line(BASELINE_NAMES[n], false, row(n)!)] : []))],
    },
  ];
  const subset = results.allergy_medicine;
  if (subset && subset.rows.length > 0) {
    views.push({
      key: "allergy-medicine",
      button: `Allergies and medicines only (${fmt(subset.key_facts)}), with Azure`,
      others: "of the others",
      lines: subset.rows.map((r) => line(r.method, r.key === "full_tool", r)),
      details: {
        summary: "Details: about this view and Azure",
        text:
          "Keyword search and medSpaCy only look for allergies and medicines, so this view counts only those facts. " +
          "Azure is Microsoft Azure Text Analytics for Health, a commercial clinical tool, not ours; it was scored on these facts only. " +
          "Our tool was tuned on these record layouts and Azure was not, and some of Azure's misses come from how we translated its output. " +
          "This is not a claim about Azure in general.",
        link: { href: WRITE_UP, label: "The full caveats are in the write-up." },
      },
    });
  }
  return views;
}

// The build chart: false alarms at each step of the tool, split into repeats and the rest.
function BuildChart({ results }: { results: Results }) {
  const steps = [4, 5, 6, 7].map((n) => full(results.rows.find((r) => r.row === n)));
  if (steps.some((s) => s === null)) return null;
  const rows = steps as FullRow[];
  const [, , beforeMerge, tool] = rows;
  const max = niceMax(rows.map((r) => r.false_alarms));
  // The title only says "most are repeats" when the numbers say so.
  const mostlyRepeats = rows.slice(0, 3).every((r) => r.repeats * 2 > r.false_alarms);
  const slips = results.answer_key_slips;
  return (
    <Card className="flex flex-col gap-3">
      <div>
        <h2 className="text-base font-semibold">
          {mostlyRepeats ? "Most false alarms are repeats until the merge rules" : "False alarms at each step of the tool"}: {fmt(beforeMerge.false_alarms)} down to {fmt(tool.false_alarms)}.
        </h2>
        <p className="flex flex-wrap items-center gap-x-4 text-quiet">
          <span>False alarms (fewer is better)</span>
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 bg-bar-repeat" aria-hidden="true" />
            Repeats
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 bg-bar-other" aria-hidden="true" />
            Other false alarms
          </span>
        </p>
      </div>
      <div>
        {rows.map((r) => {
          const isTool = r.row === 7;
          return (
            <BarRow
              key={r.row}
              label={BUILD_STEPS[r.row]}
              strong={isTool}
              labelWidth="sm:w-56"
              parts={[
                { n: r.repeats, className: "bg-bar-repeat" },
                { n: r.false_alarms - r.repeats, className: isTool ? "bg-accent" : "bg-bar-other" },
              ]}
              max={max}
              value={fmt(r.false_alarms)}
              note={`${fmt(r.repeats)} repeats, ${fmt(r.missed)} missed`}
            />
          );
        })}
        <Axis max={max} labelWidth="sm:w-56" />
      </div>
      <p className="text-xs text-quiet">
        A repeat is a correct fact listed again. Merging raises misses from {fmt(beforeMerge.missed)} to {fmt(tool.missed)}
        {typeof slips === "number" && slips > 0 && `; ${fmt(slips)} of the ${fmt(tool.missed)} are double spaces in our answer key`}.
      </p>
      <CheaperModel results={results} />
    </Card>
  );
}

// The cheaper model's result as one line of text (not a bar).
function CheaperModel({ results }: { results: Results }) {
  const haiku = results.rows.find((r) => r.row === 8);
  if (!haiku || haiku.missed === null || haiku.false_alarms === null) return null;
  const cents = (name: string) => results.cost_per_patient?.find((c) => c.model.includes(name))?.us_cents;
  const [cheap, main] = [cents("Haiku"), cents("Sonnet")];
  return (
    <p className="text-xs">
      <span className="font-semibold">Cheaper model (Claude Haiku 5.5):</span> {fmt(haiku.missed)} missed, {fmt(haiku.false_alarms)} false alarms
      {typeof cheap === "number" && typeof main === "number" && `, ${cheap} US cents per patient against ${main}`}.
    </p>
  );
}

// By age and sex: one row per group, the full tool beside keyword search.
function AgeSexTable({ results }: { results: Results }) {
  const groups = (results.by_age_sex ?? []).filter((g) => g.key_facts !== null && g.tool_missed !== null && g.baseline_missed !== null && g.tool_false_alarms !== null && g.baseline_false_alarms !== null);
  if (groups.length === 0) return null;
  const rate = (facts: number, missed: number) => (facts > 0 ? (facts - missed) / facts : 1);
  const toolRates = groups.map((g) => rate(g.key_facts!, g.tool_missed!));
  const lowest = Math.min(...toolRates);
  const each = new Set(groups.map((g) => g.patients));
  return (
    <Box
      title={`By age and sex: the tool finds at least ${(lowest * 100).toFixed(1)}% of facts in every group`}
      id="age-sex"
      right={each.size === 1 && groups[0].patients !== null ? `${groups[0].patients} patients per group` : undefined}
    >
      {/* A wide table: on a narrow screen it scrolls inside its own box, not the page. */}
      <div className="overflow-x-auto">
        <table className="dt">
          <thead>
            <tr>
              <th scope="col" rowSpan={2}>Age</th>
              <th scope="col" rowSpan={2}>Sex</th>
              <th scope="col" rowSpan={2} className="num">Facts</th>
              <th scope="colgroup" colSpan={3} className="text-center! text-accent!">Full tool</th>
              <th scope="colgroup" colSpan={3} className="text-center!">Keyword search</th>
            </tr>
            <tr>
              <th scope="col" className="num">Missed</th>
              <th scope="col" className="num">Found</th>
              <th scope="col" className="num">False alarms</th>
              <th scope="col" className="num">Missed</th>
              <th scope="col" className="num">Found</th>
              <th scope="col" className="num">False alarms</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((g, i) => (
              <tr key={`${g.age_band}-${g.sex}`}>
                <td className="whitespace-nowrap">{g.age_band}</td>
                <td>
                  {g.sex === "F" ? "Female" : g.sex === "M" ? "Male" : g.sex}
                  {toolRates[i] === lowest && <span className="ml-2 text-xs text-quiet">Lowest for the tool</span>}
                </td>
                <td className="num">{fmt(g.key_facts!)}</td>
                <td className="num font-semibold">{fmt(g.tool_missed!)}</td>
                <td className="num font-semibold">{percent(g.key_facts! - g.tool_missed!, g.key_facts!)}</td>
                <td className="num font-semibold">{fmt(g.tool_false_alarms!)}</td>
                <td className="num">{fmt(g.baseline_missed!)}</td>
                <td className="num">{percent(g.key_facts! - g.baseline_missed!, g.key_facts!)}</td>
                <td className="num">{fmt(g.baseline_false_alarms!)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Box>
  );
}

// Planted traps: how many of each kind the full tool and keyword search caught.
// T90: a judge may not know what a planted trap is, so one plain line says it, and each
// trap's name opens to what it is and the right answer (a tap on a phone; on a laptop the
// same words also show when the mouse rests on the name).
function TrapsTable({ results }: { results: Results }) {
  const traps = results.traps ?? [];
  if (traps.length === 0) return null;
  const planted = traps.every((t) => typeof t.planted === "number") ? traps.reduce((a, t) => a + t.planted!, 0) : null;
  const overtaken = traps.reduce((a, t) => a + (t.overtaken ?? 0), 0);
  return (
    <Box title="Planted traps caught" id="traps" right={`${fmt(traps.reduce((a, t) => a + t.scored, 0))} scored`}>
      <p className="border-b border-line px-3 py-2 text-sm">
        <span className="font-semibold">What is a planted trap?</span> A change we made on purpose to a patient&rsquo;s
        three records, to see whether the tool falls for it. We know the right answer for each one.
        {traps.some((t) => t.meaning) && " Tap a trap's name to see what it is."}
      </p>
      <table className="dt">
        <thead>
          <tr>
            <th scope="col">Trap</th>
            <th scope="col" className="num text-accent!">Full tool</th>
            <th scope="col" className="num">Keyword search</th>
          </tr>
        </thead>
        <tbody>
          {traps.map((t) => (
            <tr key={t.kind}>
              <td>
                {t.meaning ? (
                  <details>
                    <summary title={t.meaning} className="cursor-pointer underline decoration-dotted underline-offset-4">
                      {t.label}
                    </summary>
                    <p className="mt-1 max-w-prose text-sm text-quiet">{t.meaning}</p>
                  </details>
                ) : (
                  t.label
                )}
              </td>
              <td className="num align-top font-semibold">
                {fmt(t.tool_caught)} of {fmt(t.scored)}
              </td>
              <td className="num align-top">
                {fmt(t.baseline_caught)} of {fmt(t.scored)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="border-t border-line px-3 py-2 text-xs text-quiet">
        {planted !== null && `${fmt(planted)} traps planted, up to 2 per patient. `}
        {overtaken > 0 && `${fmt(overtaken)} are left out of the count because a later record changed the right answer. `}
        Keyword search catches the last two only because it keeps every line it finds; it cannot tell a stopped medicine
        from a current one, or an old dose from a new one.
      </p>
    </Box>
  );
}

// The failure examples: each title opens its explanation.
function Failures({ results }: { results: Results }) {
  return (
    <Box title="Where the tool got it wrong" id="wrong">
      {results.failure_examples.length === 0 ? (
        <p className="px-3 py-2 text-quiet">Not added yet. Three real failure examples are added after scoring.</p>
      ) : (
        <ul>
          {results.failure_examples.map((ex) => (
            <li key={ex.title} className="border-b border-line px-3 py-1.5 last:border-b-0">
              <details>
                <summary>{ex.title}</summary>
                <p className="mt-1">{ex.explanation}</p>
              </details>
            </li>
          ))}
        </ul>
      )}
    </Box>
  );
}

// The tool's steps in order, each saying whether the AI or plain code does it.
const STEPS: { title: string; who: string; what: string }[] = [
  { title: "Three records", who: "Input", what: "One record from each hospital, in three layouts." },
  { title: "Extract", who: "Claude (AI)", what: "Reads each record and lists every fact with a word-for-word quote." },
  { title: "Check", who: "Code, no AI", what: "Checks each quote is word for word and each name is on the drug list, and turns brand names into generic names." },
  { title: "Merge", who: "Code, no AI", what: "Six fixed rules join the three lists and keep every disagreement." },
  { title: "One record", who: "Output", what: "One record for the doctor, with the source of every fact." },
];

// How the test was run, how the tool works, the limits, the cost and the word search:
// everything a judge may want to check, folded until asked for.
function Method({ results }: { results: Results | null }) {
  return (
    <details className="rounded-box border border-line bg-surface">
      <summary className="px-3 py-2 font-semibold">Details: method, limits, cost (Sonnet against Haiku)</summary>
      <div className="flex flex-col gap-4 border-t border-line p-3">
        <section aria-labelledby="test-heading">
          <h2 id="test-heading" className="font-semibold">
            The test
          </h2>
          <ul className="mt-1 flex list-disc flex-col gap-1 pl-5">
            <li>All patients are synthetic (Synthea). No real patient records are used.</li>
            <li>
              Each patient has three hospital records in three different layouts: a table, a free-text letter, and a
              sheet that uses brand names.
            </li>
            <li>The correct answer for each patient is built by code from the patient&rsquo;s history, not by the AI.</li>
            <li>
              The prompt was tuned on 20 working patients only. The tool was then frozen and run once on {results?.patients ?? 160} held-out
              patients it had never seen, 20 in each age band and sex group.
            </li>
            <li>Keyword search, medSpaCy and keyword search with rules are baselines that use no AI. The second chart builds our tool up one step at a time.</li>
            <li>
              The numbers on this page are read by a script from the results files in outputs/results/heldout/ on GitHub
              (buildup_table.csv, azure_line.csv, by_age_sex.csv, traps_by_type.csv, cost_per_patient.csv, omission_line.csv).
            </li>
          </ul>
        </section>
        <section aria-labelledby="works-heading">
          <h2 id="works-heading" className="font-semibold">
            How the tool works
          </h2>
          <ol className="mt-1 flex list-decimal flex-col gap-1 pl-5">
            {STEPS.map((s) => (
              <li key={s.title}>
                <span className="font-medium">{s.title}</span> <span className="text-quiet">({s.who})</span>: {s.what}
              </li>
            ))}
          </ol>
          <p className="mt-1 text-quiet">Only the Extract step uses AI. Check and Merge are plain code.</p>
        </section>
        <section aria-labelledby="limits-heading">
          <h2 id="limits-heading" className="font-semibold">
            Limits
          </h2>
          <ul className="mt-1 flex list-disc flex-col gap-1 pl-5">
            <li>
              <span className="font-medium">Synthetic data only.</span> Every patient is made up (Synthea), so the
              results say how the tool does on these records, not on real hospital records.
            </li>
            <li>
              <span className="font-medium">Neater than real records.</span> The three hospital layouts come from our
              own templates. Real records are messier: handwriting, scans, typing mistakes and missing sections.
            </li>
            <li>
              <span className="font-medium">One main model.</span> The tool uses Claude Sonnet 5.5. Claude Haiku 5.5 is
              only a comparison, and no other model was tested.
            </li>
          </ul>
        </section>
        {results && (
          <>
            <CostLine entries={results.cost_per_patient} rows={results.rows} />
            <section aria-labelledby="omission-heading">
              <h2 id="omission-heading" className="font-semibold">
                Double-check: word search
              </h2>
              <p className="mt-1">{results.omission_check ?? "Not run yet."}</p>
            </section>
          </>
        )}
      </div>
    </details>
  );
}

// The keyword baseline and the side-by-side view for one patient (moved here from the
// doctor screen in T81). A plain form: each button opens that view on the doctor screen.
function BaselineOnePatient() {
  return (
    <details className="rounded-box border border-line bg-surface">
      <summary className="px-3 py-2 font-semibold">Baseline on one patient</summary>
      <form action="/" method="get" className="flex flex-wrap items-center gap-2 border-t border-line p-3">
        <label htmlFor="compare-id" className="text-quiet">
          Patient ID
        </label>
        <input id="compare-id" name="id" type="text" defaultValue={SAMPLE_IDS.includes("D001") ? "D001" : (SAMPLE_IDS[0] ?? "")} autoComplete="off" className="h-8 w-24 rounded-ctl border border-line-strong bg-surface px-2" />
        <button type="submit" name="view" value="baseline" className="h-8 rounded-ctl border border-line-strong bg-surface px-3 font-medium">
          Baseline (keyword search)
        </button>
        <button type="submit" name="view" value="compare" className="h-8 rounded-ctl border border-line-strong bg-surface px-3 font-medium">
          Compare side by side
        </button>
      </form>
    </details>
  );
}

// Disagreements between hospitals shown, as one clear line near the top.
function Disagreements({ results }: { results: Results }) {
  const row = (n: number) => results.rows.find((r) => r.row === n);
  const tool = row(7);
  if (!tool || tool.conflicts_shown === null || tool.conflicts_total == null) return null;
  const rest = [3, 1, 2].flatMap((n) => {
    const r = row(n);
    return r && r.conflicts_shown !== null ? [`${BASELINE_NAMES[n]} ${fmt(r.conflicts_shown)}`] : [];
  });
  return (
    <p className="text-base">
      <span className="font-semibold">
        Disagreements between hospitals shown: full tool {fmt(tool.conflicts_shown)} of {fmt(tool.conflicts_total)}.
      </span>{" "}
      {rest.length > 0 && `${rest.join(", ")}.`}
    </p>
  );
}

// Reads the results file and shows the page, the empty state or the failed state.
async function Body() {
  const load = await loadResults();

  if (load.state !== "ok") {
    return (
      <Page>
        <h1 className="text-xl font-semibold">How we tested</h1>
        {load.state === "empty" ? (
          <Card role="status">
            <p className="font-semibold">No results to show yet.</p>
            <p className="mt-1">The results appear here once the held-out run has been scored.</p>
          </Card>
        ) : (
          <Card role="alert" className="border-2 border-warn-line">
            <p className="font-semibold">The results could not be loaded.</p>
            <p className="mt-1">{load.reason} No numbers are shown rather than showing wrong ones.</p>
          </Card>
        )}
        <Method results={null} />
      </Page>
    );
  }

  const results = load.results;
  const views = methodViews(results);
  const tool = results.rows.find((r) => r.row === 7);
  return (
    <Page>
      {results.status === "placeholder" && (
        <Card role="status" className="border-dashed border-ink">
          <p className="font-semibold">Placeholder: no results yet.</p>
          <p className="mt-1">The real numbers appear here after the one run on the held-out patients.</p>
        </Card>
      )}

      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <h1 className="text-xl font-semibold">How we tested</h1>
          {/* The dataset, stated once for the whole page. */}
          {results.patients !== null && tool?.key_facts != null && (
            <p className="text-quiet">
              {fmt(results.patients)} held-out synthetic patients, {fmt(tool.key_facts)} facts, scored once after the tool was frozen.
            </p>
          )}
        </div>
        <Disagreements results={results} />
      </div>

      {views.length > 0 ? (
        <Card>
          <MethodChart views={views} />
        </Card>
      ) : (
        <Card role="status">
          <p className="font-semibold">Not run yet</p>
          <p className="mt-1 text-quiet">The full tool and the baselines are compared here once the held-out results are in.</p>
        </Card>
      )}

      <BuildChart results={results} />

      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <AgeSexTable results={results} />
        <div className="flex min-w-0 flex-col gap-4">
          <TrapsTable results={results} />
          <Failures results={results} />
        </div>
      </div>

      <BaselineOnePatient />
      <Method results={results} />
    </Page>
  );
}

export default function HowWeTested() {
  return (
    <Suspense
      fallback={
        <Page>
          <p>Loading results…</p>
        </Page>
      }
    >
      <Body />
    </Suspense>
  );
}
