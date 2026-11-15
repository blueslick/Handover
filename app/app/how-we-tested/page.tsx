// "How we tested" tab: how the test was run, the results and the failure examples.
// Reads app/data/results.json only (see lib/results.ts). Until T39 the file was a
// placeholder, so every number can still show "Not run yet".
// T75 (Minimal look): the first screen shows the headline, one chart and three numbers.
// Below it (T78): the age and sex chart and the planted traps chart. How the tool works and
// the limits fold open below those; the test, the failure examples, the cost and the word search are in the
// right-hand panel. Nothing from the earlier tab was removed.
import { Suspense } from "react";
import { loadResults, type ResultRow, type Results } from "@/lib/results";
import Page, { Card } from "../components/Page";
import CostLine from "./CostLine";
import StepChart from "./StepChart";
import AgeSexChart from "./AgeSexChart";
import TrapsChart from "./TrapsChart";

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
    <details className="group/fold rounded-3xl bg-white">
      <summary className="flex items-center justify-between gap-4 p-5 sm:px-6">
        <h2 className="text-lg font-medium">{title}</h2>
        <span className="rounded-full bg-mint px-4 py-1 text-sm font-medium text-rail-ink">
          <span className="group-open/fold:hidden">Show</span>
          <span className="hidden group-open/fold:inline">Hide</span>
        </span>
      </summary>
      <div className="px-5 pb-5 sm:px-6 sm:pb-6">{children}</div>
    </details>
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

// T71 item 32: the tool's steps as plain boxes (HTML, not an image), each saying whether
// Claude or plain code does it. One wide row per step, reading down the page.
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
      {/* Abby's review: five boxes side by side were too narrow to read, so each step is
          now one full-width row, top to bottom, with an arrow down between them. */}
      <ol className="flex flex-col">
        {STEPS.map((s, i) => (
          <li key={s.title} className="flex flex-col">
            <div className={`flex flex-col gap-x-6 gap-y-1 rounded-2xl px-5 py-3 sm:flex-row sm:items-center ${s.ai ? "bg-rail text-white" : "bg-mint"}`}>
              <div className="sm:w-40 sm:shrink-0">
                <p className="font-medium">{s.title}</p>
                <p className="text-sm">{s.who}</p>
              </div>
              <p>{s.what}</p>
            </div>
            {i < STEPS.length - 1 && (
              <span aria-hidden="true" className="self-center py-0.5 text-xl leading-none text-rail">
                ↓
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
            In the first chart, each bar from left to right adds one step, so you can see what each step adds. The
            last bar runs the full tool on a second, cheaper model.
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
                    <details className="group/fail py-3">
                      <summary className="flex items-start justify-between gap-3 font-normal">
                        <span>{ex.title}</span>
                        <span className="shrink-0 text-sm font-medium text-rail-ink underline underline-offset-2">
                          <span className="group-open/fail:hidden">Show</span>
                          <span className="hidden group-open/fail:inline">Hide</span>
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

      {/* T78 (Daniel): the full table and the age and sex table were hard to read, so they
          are replaced by graphs. The exact numbers stay in the write-up and on GitHub. */}
      <Card>
        <AgeSexChart groups={results.by_age_sex} />
      </Card>
      <Card>
        <TrapsChart traps={results.traps} />
      </Card>
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
