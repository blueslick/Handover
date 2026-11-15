// "How we tested" tab: how the test was run, the results and the failure examples.
// Reads app/data/results.json only (see lib/results.ts). Until T39 the file was a
// placeholder, so every number can still show "Not run yet".
// T75 (Minimal look): the first screen shows the headline, one chart and three numbers.
// The full table, the age and sex results, how the tool works and the limits fold open
// below; the test, the failure examples, the cost and the word search are in the
// right-hand panel. Nothing from the earlier tab was removed.
import { Suspense } from "react";
import { loadResults, type AgeSexRow, type ResultRow, type Results } from "@/lib/results";
import Page, { Card } from "../components/Page";
import Tip from "../components/Tip";
import CostLine from "./CostLine";
import StepChart from "./StepChart";

export const metadata = { title: "How we tested · Handover" };

// A count, or the words "Not run yet" when there is no number.
function count(n: number | null): string {
  return n === null ? "Not run yet" : n.toLocaleString("en-GB");
}

// "3 of 120" when both numbers exist, otherwise just the count.
function outOf(n: number | null, total: number | null): string {
  if (n === null) return "Not run yet";
  return total === null ? n.toLocaleString("en-GB") : `${n.toLocaleString("en-GB")} of ${total.toLocaleString("en-GB")}`;
}

// A section that opens on a tap, with "Show" or "Hide" written on it.
function Fold({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <details className="group rounded-3xl bg-white">
      <summary className="flex items-center justify-between gap-4 p-5 sm:px-6">
        <h2 className="text-lg font-medium">{title}</h2>
        <span className="rounded-full bg-mint px-4 py-1 text-sm font-medium text-rail-ink">
          <span className="group-open:hidden">Show</span>
          <span className="hidden group-open:inline">Hide</span>
        </span>
      </summary>
      <div className="px-5 pb-5 sm:px-6 sm:pb-6">{children}</div>
    </details>
  );
}

// What each column of the table means (shown on hover over the heading, and listed under the table).
const COLUMN_MEANING = {
  missed: "A fact in the answer key that the method did not find.",
  false_alarms: "A fact the method reported that is not in the answer key.",
  wrong_status:
    "The right drug or allergy with the wrong label, for example “current” for a medicine that was stopped. It also counts once as missed and once as a false alarm.",
  conflicts: "Places where hospitals disagree that the method showed side by side.",
};

// T71 item 30: the two rows the headline compares get a tag in words and their own
// background, so they don't rely on colour alone.
const ROW_MARKS: Record<number, { word: string; row: string; tag: string }> = {
  1: { word: "Baseline", row: "bg-peach", tag: "bg-alert text-white" },
  7: { word: "Full tool", row: "bg-leaf font-medium", tag: "bg-rail text-white" },
};

const th = "px-3 py-2 text-left text-sm font-normal text-soft whitespace-nowrap";
const td = "px-3 py-2.5";

// The build-up table. Scrolls sideways on a phone rather than squashing the columns.
function ResultsTable({ rows }: { rows: ResultRow[] }) {
  return (
    <>
      <p className="text-sm text-soft">
        {rows[0]?.key_facts != null ? `All ${rows[0].key_facts.toLocaleString("en-GB")} facts` : "All facts"} in the
        held-out answer keys (allergies, medicines, diagnoses and operations). Rows 1 to 7 each add one step to the
        row above. Row 8 is the full tool again on a second, cheaper model.
      </p>
      <p className="mt-2 text-sm text-soft sm:hidden">Scroll sideways to see every column.</p>
      <div className="mt-2 overflow-x-auto">
        <table className="min-w-full border-separate border-spacing-y-1">
          <caption className="sr-only">Results for each method, one row per method</caption>
          <thead>
            <tr>
              <th scope="col" className={th}>Row</th>
              <th scope="col" className={`${th} min-w-[16rem]`}>Method</th>
              <th scope="col" className={th}>Uses AI</th>
              <th scope="col" className={th}><Tip tip={COLUMN_MEANING.missed}>Missed</Tip></th>
              <th scope="col" className={th}><Tip tip={COLUMN_MEANING.false_alarms}>False alarms</Tip></th>
              <th scope="col" className={th}><Tip tip={COLUMN_MEANING.wrong_status}>Wrong status</Tip></th>
              <th scope="col" className={th}><Tip tip={COLUMN_MEANING.conflicts}>Conflicts shown</Tip></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const mark = ROW_MARKS[r.row];
              return (
                <tr key={r.row} className={mark?.row}>
                  <td className={`${td} rounded-l-2xl`}>{r.row}</td>
                  <th scope="row" className={`${td} text-left font-normal`}>
                    {mark && <span className={`mr-2 inline-block rounded-full px-3 py-0.5 text-sm font-medium ${mark.tag}`}>{mark.word}</span>}
                    {r.method}
                  </th>
                  <td className={td}>{r.uses_ai ? "Yes" : "No"}</td>
                  <td className={td}>{outOf(r.missed, r.key_facts)}</td>
                  <td className={td}>{count(r.false_alarms)}</td>
                  <td className={td}>{count(r.wrong_status)}</td>
                  <td className={`${td} rounded-r-2xl`}>{outOf(r.conflicts_shown, r.conflicts_total ?? null)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <h3 className="mt-4 font-medium">What the columns mean</h3>
      <ul className="mt-1 list-disc pl-5 text-sm">
        <li><span className="font-medium">Missed:</span> {COLUMN_MEANING.missed}</li>
        <li><span className="font-medium">False alarms:</span> {COLUMN_MEANING.false_alarms}</li>
        <li><span className="font-medium">Wrong status:</span> {COLUMN_MEANING.wrong_status}</li>
        <li><span className="font-medium">Conflicts shown:</span> {COLUMN_MEANING.conflicts}</li>
      </ul>
      <p className="mt-2 text-sm">Missed cases and false alarms are counted separately, because they cause different harms.</p>
    </>
  );
}

// T71 item 29: one headline sentence, the full tool (row 7) against the keyword baseline
// (row 1), filled only from the results file. Until the numbers are in, it says so.
function Headline({ results }: { results: Results }) {
  const tool = results.rows.find((r) => r.row === 7);
  const base = results.rows.find((r) => r.row === 1);
  const ready = (r?: ResultRow) => r !== undefined && r.missed !== null && r.false_alarms !== null;
  if (!ready(tool) || !ready(base)) {
    return (
      <>
        <p className="text-3xl font-medium leading-tight">Not run yet</p>
        <p className="mt-2 text-soft">The full tool and the baseline are compared here once the held-out results are in.</p>
      </>
    );
  }
  const n = (x: number | null) => (x === null ? "?" : x.toLocaleString("en-GB"));
  const who = results.patients !== null ? `On ${n(results.patients)} held-out patients, the` : "The";
  return (
    <>
      <p className="text-3xl sm:text-4xl font-medium leading-tight">
        {n(tool!.missed)}
        {tool!.key_facts !== null && ` of ${n(tool!.key_facts)}`} facts missed
      </p>
      <p className="mt-2 text-soft">
        {who} full tool missed {n(tool!.missed)}
        {tool!.key_facts !== null && ` of ${n(tool!.key_facts)}`} facts with {n(tool!.false_alarms)} false alarms. The
        keyword baseline missed {n(base!.missed)} with {n(base!.false_alarms)} false alarms.
      </p>
    </>
  );
}

// The three numbers under the chart: the full tool (row 7), with the keyword baseline
// (row 1) in small print. Worked out from the results file, never typed.
function NumberCards({ results }: { results: Results }) {
  const tool = results.rows.find((r) => r.row === 7);
  const base = results.rows.find((r) => r.row === 1);
  if (!tool || !base) return null;
  const found = (r: ResultRow) => (r.key_facts !== null && r.missed !== null && r.key_facts > 0 ? `${(((r.key_facts - r.missed) / r.key_facts) * 100).toFixed(1)}%` : "Not run yet");
  return (
    <div className="grid gap-5 sm:grid-cols-3">
      <section className="flex flex-col gap-1 rounded-3xl bg-rail p-6 text-white">
        <h2 className="font-normal">Facts found</h2>
        <p className="mt-auto pt-4 text-5xl font-medium leading-none">{found(tool)}</p>
        <p className="text-sm">Keyword search: {found(base)}</p>
      </section>
      <Card className="flex flex-col gap-1">
        <h2 className="font-normal">False alarms</h2>
        <p className="mt-auto pt-4 text-4xl font-medium leading-none">{count(tool.false_alarms)}</p>
        <p className="text-sm text-soft">Keyword search: {count(base.false_alarms)}</p>
      </Card>
      <Card className="flex flex-col gap-1">
        <h2 className="font-normal">Disagreements shown</h2>
        <p className="mt-auto pt-4 text-4xl font-medium leading-none">{outOf(tool.conflicts_shown, tool.conflicts_total ?? null)}</p>
        <p className="text-sm text-soft">Keyword search: {count(base.conflicts_shown)}</p>
      </Card>
    </div>
  );
}

// T71 item 31: the full tool next to the keyword baseline for each age band and sex,
// all facts. Says "Not run yet" when the results file has no groups.
function AgeSexTable({ groups }: { groups?: AgeSexRow[] }) {
  if (!groups || groups.length === 0) return <p>Not run yet.</p>;
  // The group where the full tool missed the largest share of facts, marked in words.
  const share = (g: AgeSexRow) => (g.tool_missed !== null && g.key_facts ? g.tool_missed / g.key_facts : -1);
  const worst = groups.reduce((a, b) => (share(b) > share(a) ? b : a));
  return (
    <>
      <p className="text-sm text-soft">
        Every held-out patient is in one of eight groups: four age bands, each split by sex. The full tool is
        row 7 of the table and the baseline is row 1.
      </p>
      <p className="mt-2 text-sm text-soft sm:hidden">Scroll sideways to see every column.</p>
      <div className="mt-2 overflow-x-auto">
        <table className="min-w-full border-separate border-spacing-y-1">
          <caption className="sr-only">Missed facts and false alarms for each age band and sex</caption>
          <thead>
            <tr>
              <th scope="col" className={th}>Age band</th>
              <th scope="col" className={th}>Sex</th>
              <th scope="col" className={th}>Patients</th>
              <th scope="col" className={th}>Full tool: missed</th>
              <th scope="col" className={th}>Full tool: false alarms</th>
              <th scope="col" className={th}>Baseline: missed</th>
              <th scope="col" className={th}>Baseline: false alarms</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => {
              const weak = g === worst && share(g) > 0;
              return (
                <tr key={`${g.age_band}-${g.sex}`} className={weak ? "bg-peach" : undefined}>
                  <th scope="row" className={`${td} rounded-l-2xl text-left font-normal`}>{g.age_band}</th>
                  <td className={td}>
                    {g.sex === "F" ? "Female" : g.sex === "M" ? "Male" : g.sex}
                    {weak && <span className="ml-2 rounded-full bg-alert px-3 py-0.5 text-sm font-medium text-white">Weakest group</span>}
                  </td>
                  <td className={td}>{count(g.patients)}</td>
                  <td className={td}>{outOf(g.tool_missed, g.key_facts)}</td>
                  <td className={td}>{count(g.tool_false_alarms)}</td>
                  <td className={td}>{outOf(g.baseline_missed, g.key_facts)}</td>
                  <td className={`${td} rounded-r-2xl`}>{count(g.baseline_false_alarms)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

// T71 item 32: the tool's steps as plain boxes (HTML, not an image), each saying whether
// Claude or plain code does it. Stacks down the page on a phone, runs across on a laptop.
const STEPS: { title: string; who: string; what: string; ai?: boolean }[] = [
  { title: "Three records", who: "Input", what: "One record from each hospital, in three layouts." },
  { title: "Extract", who: "Claude (AI)", what: "Reads each record and lists every fact with a word-for-word quote.", ai: true },
  { title: "Check", who: "Code, no AI", what: "Checks each quote is word for word and each name is on the drug list, and turns brand names into generic names." },
  { title: "Merge", who: "Code, no AI", what: "Six fixed rules join the three lists and keep every disagreement." },
  { title: "One record", who: "Output", what: "One record for the doctor, with the source of every fact." },
];

function WorkflowDiagram() {
  return (
    <>
      <ol className="flex flex-col gap-2 md:flex-row md:items-stretch md:gap-0">
        {STEPS.map((s, i) => (
          <li key={s.title} className="flex flex-col md:flex-row md:flex-1 md:items-center">
            <div className={`flex-1 rounded-2xl p-3 ${s.ai ? "bg-rail text-white" : "bg-mint"}`}>
              <p className="font-medium">{s.title}</p>
              <p className="text-sm font-medium">{s.who}</p>
              <p className="mt-1 text-sm">{s.what}</p>
            </div>
            {i < STEPS.length - 1 && (
              <span aria-hidden="true" className="self-center px-1 text-xl text-rail md:px-2">
                <span className="md:hidden">↓</span>
                <span className="hidden md:inline">→</span>
              </span>
            )}
          </li>
        ))}
      </ol>
      <p className="mt-2 text-sm text-soft">Only the Extract step uses AI. Check and Merge are plain code.</p>
    </>
  );
}

function Limits() {
  return (
    <ul className="list-disc pl-5">
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
        only a comparison row (row 8), and no other model was tested.
      </li>
    </ul>
  );
}

// How the test was run. The same five points as before T75, behind one tap in the panel.
function TheTest({ patients }: { patients: number | null }) {
  return (
    <section aria-labelledby="test-heading">
      <h2 id="test-heading" className="text-lg font-medium">
        The test
      </h2>
      <dl className="mt-2 grid grid-cols-3 divide-x divide-sage">
        <div>
          <dt className="text-sm text-soft">Patients</dt>
          <dd className="text-xl font-medium">{patients === null ? "160" : patients}</dd>
        </div>
        <div className="pl-3">
          <dt className="text-sm text-soft">Records each</dt>
          <dd className="text-xl font-medium">3</dd>
        </div>
        <div className="pl-3">
          <dt className="text-sm text-soft">Real records</dt>
          <dd className="text-xl font-medium">0</dd>
        </div>
      </dl>
      <details className="mt-2 text-sm">
        <summary className="underline underline-offset-2">How the test worked</summary>
        <ul className="mt-2 list-disc pl-5 flex flex-col gap-1">
          <li>All patients are synthetic (Synthea). No real patient records are used.</li>
          <li>
            Each patient has three hospital records in three different layouts: a table, a free-text letter, and a
            sheet that uses brand names.
          </li>
          <li>The correct answer for each patient is built by code from the patient&rsquo;s history, not by the AI.</li>
          <li>
            The prompt was tuned on 20 working patients only. The tool was then frozen and run once on 160 held-out
            patients it had never seen, 20 in each age band and sex group.
          </li>
          <li>
            Rows 1 to 7 of the table each add one step, so you can see what each step adds. Row 8 runs the full tool
            on a second, cheaper model.
          </li>
        </ul>
      </details>
    </section>
  );
}

// The right-hand panel: the test, the failure examples, the cost and the word search.
function Aside({ results }: { results: Results | null }) {
  return (
    <>
      <TheTest patients={results?.patients ?? null} />
      {results && (
        <>
          <section aria-labelledby="wrong-heading">
            <h2 id="wrong-heading" className="text-lg font-medium">
              Where it went wrong
            </h2>
            {results.failure_examples.length === 0 ? (
              <p className="mt-2 text-soft">Not added yet. Three real failure examples are added after scoring.</p>
            ) : (
              <ul className="mt-1 divide-y divide-sage">
                {results.failure_examples.map((ex) => (
                  <li key={ex.title}>
                    <details className="group py-3">
                      <summary className="flex items-start justify-between gap-3 font-normal">
                        <span>{ex.title}</span>
                        <span className="shrink-0 text-sm font-medium text-rail-ink underline underline-offset-2">
                          <span className="group-open:hidden">Show</span>
                          <span className="hidden group-open:inline">Hide</span>
                        </span>
                      </summary>
                      <p className="mt-2 text-sm">{ex.explanation}</p>
                    </details>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <CostLine entries={results.cost_per_patient} />
          <section aria-labelledby="omission-heading" className="rounded-2xl bg-mint px-4 py-3">
            <h2 id="omission-heading" className="font-medium">
              Double-check: word search
            </h2>
            <details className="text-sm">
              <summary className="underline underline-offset-2">What it found</summary>
              <p className="mt-1">{results.omission_check ?? "Not run yet."}</p>
            </details>
          </section>
        </>
      )}
    </>
  );
}

// Reads the results file and shows the page, the empty state or the failed state.
async function Body() {
  const load = await loadResults();

  if (load.state !== "ok") {
    return (
      <Page aside={<Aside results={null} />} asideLabel="The test">
        <h1 className="text-2xl font-medium">How we tested</h1>
        {load.state === "empty" ? (
          <Card role="status">
            <p className="font-medium">No results to show yet.</p>
            <p className="mt-1">The results appear here once the held-out run has been scored.</p>
          </Card>
        ) : (
          <Card role="alert" className="border-4 border-alert">
            <p className="font-medium">The results could not be loaded.</p>
            <p className="mt-1">{load.reason} No numbers are shown rather than showing wrong ones.</p>
          </Card>
        )}
        <Fold title="How the tool works">
          <WorkflowDiagram />
        </Fold>
      </Page>
    );
  }

  const results = load.results;
  return (
    <Page aside={<Aside results={results} />} asideLabel="The test and its failures">
      {results.status === "placeholder" && (
        <Card role="status" className="border-2 border-dashed border-ink">
          <p className="font-medium">Placeholder: no results yet.</p>
          <p className="mt-1">The real numbers appear here after the one run on the held-out patients.</p>
        </Card>
      )}

      <Card>
        <h1 className="text-soft">How we tested</h1>
        <Headline results={results} />
      </Card>

      <Card>
        <StepChart rows={results.rows} />
      </Card>

      <NumberCards results={results} />

      <Fold title="All eight methods: the full table">
        <ResultsTable rows={results.rows} />
      </Fold>
      <Fold title="By age and sex">
        <AgeSexTable groups={results.by_age_sex} />
      </Fold>
      <Fold title="How the tool works">
        <WorkflowDiagram />
      </Fold>
      <Fold title="Limits">
        <Limits />
      </Fold>
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
