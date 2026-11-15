// "How we tested" tab: how the test was run, the build-up results table, and failure examples.
// Reads app/data/results.json only (see lib/results.ts). Until T39 the file is a placeholder,
// so every number shows "Not run yet".
import { Suspense } from "react";
import { loadResults, type AgeSexRow, type ResultRow, type Results } from "@/lib/results";
import CostLine from "./CostLine";

export const metadata = { title: "How we tested · Handover" };

// A count, or the words "Not run yet" when there is no number.
function count(n: number | null): string {
  return n === null ? "Not run yet" : String(n);
}

// "3 of 120" when both numbers exist, otherwise just the count.
function outOf(n: number | null, total: number | null): string {
  if (n === null) return "Not run yet";
  return total === null ? String(n) : `${n} of ${total}`;
}

// T71 item 30: the two rows the headline compares get a tag in words and a thick left
// edge, so they don't rely on colour alone.
const ROW_MARKS: Record<number, string> = { 1: "Baseline", 7: "Full tool" };

// The build-up table. Scrolls sideways on a phone rather than squashing the columns.
function ResultsTable({ rows }: { rows: ResultRow[] }) {
  return (
    <>
    <p className="mt-2 text-sm text-zinc-700">
      {rows[0]?.key_facts != null ? `All ${rows[0].key_facts.toLocaleString("en-GB")} facts` : "All facts"} in the
      held-out answer keys (allergies, medicines, diagnoses and operations). Rows 1 to 7
      each add one step to the row above. Row 8 is the full tool again on a second, cheaper model.
    </p>
    <div className="mt-2 overflow-x-auto">
      <table className="min-w-full border border-zinc-400 text-sm">
        <caption className="sr-only">Results for each method, one row per method</caption>
        <thead className="bg-zinc-100">
          <tr>
            <th scope="col" className="border border-zinc-400 px-2 py-1 text-left">Row</th>
            <th scope="col" className="border border-zinc-400 px-2 py-1 text-left">Method</th>
            <th scope="col" className="border border-zinc-400 px-2 py-1 text-left">Uses AI</th>
            <th scope="col" className="border border-zinc-400 px-2 py-1 text-left">Missed</th>
            <th scope="col" className="border border-zinc-400 px-2 py-1 text-left">False alarms</th>
            <th scope="col" className="border border-zinc-400 px-2 py-1 text-left">Wrong status</th>
            <th scope="col" className="border border-zinc-400 px-2 py-1 text-left">Conflicts shown</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const mark = ROW_MARKS[r.row];
            return (
            <tr key={r.row} className={mark ? "bg-zinc-50 font-semibold" : undefined}>
              <td
                className={`border border-zinc-400 px-2 py-1 ${mark ? "border-l-8 border-l-zinc-900" : ""}`}
              >
                {r.row}
              </td>
              <th scope="row" className="border border-zinc-400 px-2 py-1 text-left font-medium">
                {mark && (
                  <span className="mr-2 inline-block rounded border-2 border-zinc-900 bg-white px-1 text-xs font-bold uppercase">
                    {mark}
                  </span>
                )}
                {r.method}
              </th>
              <td className="border border-zinc-400 px-2 py-1">{r.uses_ai ? "Yes" : "No"}</td>
              <td className="border border-zinc-400 px-2 py-1">{outOf(r.missed, r.key_facts)}</td>
              <td className="border border-zinc-400 px-2 py-1">{count(r.false_alarms)}</td>
              <td className="border border-zinc-400 px-2 py-1">{count(r.wrong_status)}</td>
              <td className="border border-zinc-400 px-2 py-1">{outOf(r.conflicts_shown, r.conflicts_total ?? null)}</td>
            </tr>
            );
          })}
        </tbody>
      </table>
    </div>
    </>
  );
}

// T71 item 29: one headline line, the full tool (row 7) against the keyword baseline
// (row 1), filled only from the results file. Until the numbers are in, it says so.
function Headline({ results }: { results: Results }) {
  const tool = results.rows.find((r) => r.row === 7);
  const base = results.rows.find((r) => r.row === 1);
  const ready = (r?: ResultRow) => r !== undefined && r.missed !== null && r.false_alarms !== null;
  if (!ready(tool) || !ready(base)) {
    return (
      <p className="mt-2 text-lg font-semibold">
        Headline: not run yet. The full tool and the baseline are compared here once the held-out results are in.
      </p>
    );
  }
  const n = (x: number | null) => (x === null ? "?" : x.toLocaleString("en-GB"));
  const who = results.patients !== null ? `On ${n(results.patients)} held-out patients, the` : "The";
  return (
    <p className="mt-2 text-lg font-semibold">
      {who} full tool missed {n(tool!.missed)}
      {tool!.key_facts !== null && ` of ${n(tool!.key_facts)}`} facts with {n(tool!.false_alarms)} false alarms. The
      keyword baseline missed {n(base!.missed)} with {n(base!.false_alarms)} false alarms.
    </p>
  );
}

// T71 item 31: the full tool next to the keyword baseline for each age band and sex,
// all facts. Says "Not run yet" when the results file has no groups.
function AgeSexTable({ groups }: { groups?: AgeSexRow[] }) {
  const cell = "border border-zinc-400 px-2 py-1";
  return (
    <section className="mt-6">
      <h3 className="text-lg font-semibold">By age and sex</h3>
      {!groups || groups.length === 0 ? (
        <p className="mt-2">Not run yet.</p>
      ) : (
        <>
          <p className="mt-2 text-sm text-zinc-700">
            Every held-out patient is in one of eight groups: four age bands, each split by sex. The full tool is
            row 7 of the table above and the baseline is row 1.
          </p>
          <p className="mt-2 text-sm text-zinc-700 sm:hidden">Scroll sideways to see every column.</p>
          <div className="mt-2 overflow-x-auto">
            <table className="min-w-full border border-zinc-400 text-sm">
              <caption className="sr-only">Missed facts and false alarms for each age band and sex</caption>
              <thead className="bg-zinc-100">
                <tr>
                  <th scope="col" className={`${cell} text-left`}>Age band</th>
                  <th scope="col" className={`${cell} text-left`}>Sex</th>
                  <th scope="col" className={`${cell} text-left`}>Patients</th>
                  <th scope="col" className={`${cell} text-left`}>Full tool: missed</th>
                  <th scope="col" className={`${cell} text-left`}>Full tool: false alarms</th>
                  <th scope="col" className={`${cell} text-left`}>Baseline: missed</th>
                  <th scope="col" className={`${cell} text-left`}>Baseline: false alarms</th>
                </tr>
              </thead>
              <tbody>
                {groups.map((g) => (
                  <tr key={`${g.age_band}-${g.sex}`}>
                    <th scope="row" className={`${cell} text-left font-medium`}>{g.age_band}</th>
                    <td className={cell}>{g.sex === "F" ? "Female" : g.sex === "M" ? "Male" : g.sex}</td>
                    <td className={cell}>{count(g.patients)}</td>
                    <td className={cell}>{outOf(g.tool_missed, g.key_facts)}</td>
                    <td className={cell}>{count(g.tool_false_alarms)}</td>
                    <td className={cell}>{outOf(g.baseline_missed, g.key_facts)}</td>
                    <td className={cell}>{count(g.baseline_false_alarms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

// Everything below the intro, once the results file has loaded.
function ResultsSection({ results }: { results: Results }) {
  return (
    <>
      {results.status === "placeholder" && (
        <div role="status" className="mt-4 border-2 border-dashed border-zinc-700 rounded p-4">
          <p className="font-semibold">Placeholder: no results yet.</p>
          <p className="mt-1">
            The real numbers appear here after the one run on the held-out patients.
          </p>
        </div>
      )}

      <section className="mt-6">
        <h2 className="text-xl font-semibold">Results</h2>
        <Headline results={results} />
        {results.patients !== null && (
          <p className="mt-1 text-sm text-zinc-700">Scored on {results.patients} held-out patients.</p>
        )}
        <ResultsTable rows={results.rows} />
        <p className="mt-2 text-sm">
          <span className="font-medium">Omission check: </span>
          {results.omission_check ?? "Not run yet."}
        </p>
        <CostLine entries={results.cost_per_patient} />
        <AgeSexTable groups={results.by_age_sex} />
      </section>

      <section className="mt-6">
        <h2 className="text-xl font-semibold">What the columns mean</h2>
        <ul className="mt-2 list-disc pl-5">
          <li><span className="font-medium">Missed:</span> a fact in the answer key that the method did not find.</li>
          <li><span className="font-medium">False alarms:</span> a fact the method reported that is not in the answer key.</li>
          <li>
            <span className="font-medium">Wrong status:</span> the right drug or allergy with the wrong label, for
            example &ldquo;current&rdquo; for a medicine that was stopped. It also counts once as missed and once as a
            false alarm.
          </li>
          <li><span className="font-medium">Conflicts shown:</span> places where hospitals disagree that the method showed side by side.</li>
        </ul>
        <p className="mt-2">Missed cases and false alarms are counted separately, because they cause different harms.</p>
      </section>

      <section className="mt-6">
        <h2 className="text-xl font-semibold">Where it went wrong</h2>
        {results.failure_examples.length === 0 ? (
          <p className="mt-2">Not added yet. Three real failure examples are added after scoring.</p>
        ) : (
          <ol className="mt-2 list-decimal pl-5 flex flex-col gap-3">
            {results.failure_examples.map((ex) => (
              <li key={ex.title}>
                <p className="font-medium">{ex.title}</p>
                <p>{ex.explanation}</p>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="mt-6">
        <h2 className="text-xl font-semibold">Limits</h2>
        <ul className="mt-2 list-disc pl-5">
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
      </section>
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
    <section className="mt-6">
      <h2 className="text-xl font-semibold">How the tool works</h2>
      <ol className="mt-3 flex flex-col gap-2 md:flex-row md:items-stretch md:gap-0">
        {STEPS.map((s, i) => (
          <li key={s.title} className="flex flex-col md:flex-row md:flex-1 md:items-center">
            <div
              className={`flex-1 rounded border-2 p-3 ${
                s.ai ? "border-zinc-900 bg-zinc-100" : "border-zinc-500 bg-white"
              }`}
            >
              <p className="font-semibold">{s.title}</p>
              <p className="text-sm font-medium">{s.who}</p>
              <p className="mt-1 text-sm">{s.what}</p>
            </div>
            {i < STEPS.length - 1 && (
              <span aria-hidden="true" className="self-center px-1 text-xl md:px-2">
                <span className="md:hidden">↓</span>
                <span className="hidden md:inline">→</span>
              </span>
            )}
          </li>
        ))}
      </ol>
      <p className="mt-2 text-sm text-zinc-700">Only the Extract step uses AI. Check and Merge are plain code.</p>
    </section>
  );
}

// Reads the results file and shows the table, the empty state or the failed state.
async function ResultsBody() {
  const load = await loadResults();
  return (
    <>
      {load.state === "ok" && <ResultsSection results={load.results} />}

      {load.state === "empty" && (
        <div role="status" className="mt-6 border-2 border-zinc-700 rounded p-4">
          <p className="font-semibold">No results to show yet.</p>
          <p className="mt-1">The results table appears here once the held-out run has been scored.</p>
        </div>
      )}

      {load.state === "failed" && (
        <div role="alert" className="mt-6 border-4 border-amber-700 bg-amber-50 text-amber-950 rounded p-4">
          <p className="font-bold">The results could not be loaded.</p>
          <p className="mt-1">{load.reason} No numbers are shown rather than showing wrong ones.</p>
        </div>
      )}
    </>
  );
}

export default function HowWeTested() {
  return (
    <main className="flex-1 p-4 sm:p-8 max-w-5xl w-full mx-auto">
      <h1 className="text-3xl font-semibold">How we tested</h1>

      <section className="mt-4">
        <h2 className="text-xl font-semibold">The test</h2>
        <ul className="mt-2 list-disc pl-5">
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
          <li>Each row of the table adds one step, so you can see what each step adds.</li>
        </ul>
      </section>

      <WorkflowDiagram />

      <Suspense fallback={<p className="mt-6">Loading results…</p>}>
        <ResultsBody />
      </Suspense>
    </main>
  );
}
