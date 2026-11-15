// "How we tested" tab: how the test was run, the build-up results table, and failure examples.
// Reads app/data/results.json only (see lib/results.ts). Until T39 the file is a placeholder,
// so every number shows "Not run yet".
import { Suspense } from "react";
import { loadResults, type ResultRow, type Results } from "@/lib/results";
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

// The build-up table. Scrolls sideways on a phone rather than squashing the columns.
function ResultsTable({ rows }: { rows: ResultRow[] }) {
  return (
    <>
    <p className="mt-2 text-sm text-zinc-700">
      Allergies and medicines on the held-out patients. Rows 1 to 7 each add one step to the row above. Row 8 is the full tool again on a second, cheaper model.
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
          {rows.map((r) => (
            <tr key={r.row}>
              <td className="border border-zinc-400 px-2 py-1">{r.row}</td>
              <th scope="row" className="border border-zinc-400 px-2 py-1 text-left font-medium">
                {r.method}
              </th>
              <td className="border border-zinc-400 px-2 py-1">{r.uses_ai ? "Yes" : "No"}</td>
              <td className="border border-zinc-400 px-2 py-1">{outOf(r.missed, r.key_facts)}</td>
              <td className="border border-zinc-400 px-2 py-1">{count(r.false_alarms)}</td>
              <td className="border border-zinc-400 px-2 py-1">{count(r.wrong_status)}</td>
              <td className="border border-zinc-400 px-2 py-1">{count(r.conflicts_shown)}</td>
            </tr>
          ))}
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
    </>
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

      <Suspense fallback={<p className="mt-6">Loading results…</p>}>
        <ResultsBody />
      </Suspense>
    </main>
  );
}
