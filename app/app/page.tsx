// Doctor screen. The patient ID comes from the address (/?id=D001).
// Reads JSON from app/data/ only: no model calls, no key.
// T75 (Minimal look): the main column shows only what a doctor needs first (what to
// check, allergies, current medicines, stopped medicines, diagnoses). Tapping a line
// puts its source in the right-hand panel (address: &fact=...). "See both records" and
// "over time" open their own views (address: &show=...). Everything is a plain link,
// so it works without JavaScript and the address says what is showing.
import Link from "next/link";
import { Suspense } from "react";
import { isKnownId, liveRun, liveRuns, loadRecordState, parsePageView, SAMPLE_IDS, type LiveRun, type PageView, type View } from "@/lib/records";
import type { Fact } from "@/lib/types";
import { loadOmission } from "@/lib/omission";
import { splitSections } from "@/lib/sections";
import { formatDate, joinWords } from "@/lib/dates";
import { bannerLines } from "@/lib/banner";
import { factName } from "@/lib/names";
import { hospitalEntries } from "@/lib/timeline";
import BaselineSummary from "./components/BaselineSummary";
import CompareView from "./components/CompareView";
import ConflictView, { HospitalDot, recordsRisk } from "./components/ConflictView";
import FactList from "./components/FactList";
import FactRow from "./components/FactRow";
import OlderRecordNote from "./components/OlderRecordNote";
import OmissionBox from "./components/OmissionBox";
import Page, { Card } from "./components/Page";
import SourcePanel from "./components/SourcePanel";
import TimelineView from "./components/TimelineView";
import Tip from "./components/Tip";

type SearchParams = Promise<{ id?: string | string[]; view?: string | string[]; fact?: string | string[]; show?: string | string[] }>;
const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v)?.trim() ?? "";

// Builds an address on the doctor screen, keeping the patient and the view.
function href(id: string, o: { view?: PageView; fact?: string; show?: string } = {}): string {
  const p = new URLSearchParams({ id });
  if (o.view && o.view !== "handover") p.set("view", o.view);
  if (o.fact) p.set("fact", o.fact);
  if (o.show) p.set("show", o.show);
  return `/?${p.toString()}`;
}

// Links to the sample IDs, behind "Sample patients" and on the unknown-ID message.
// T68 item 5: grouped and labelled, so it is clear D001 is the demo patient and the
// P IDs are the working patients the tool was tuned on.
// On Daniel's laptop, live runs (T58) are listed too; on the public link there are none.
function SampleIds() {
  const live = liveRuns();
  const demo = SAMPLE_IDS.filter((id) => id.startsWith("D"));
  const working = SAMPLE_IDS.filter((id) => !id.startsWith("D"));
  const links = (ids: string[]) =>
    ids.map((id) => (
      <Link key={id} href={`/?id=${id}`} className="underline font-medium mr-2 inline-block">
        {id}
      </Link>
    ));
  return (
    <div className="mt-2 text-sm">
      {demo.length > 0 && (
        <p>
          <span className="text-soft">Demo patient: </span>
          {links(demo)}
        </p>
      )}
      {working.length > 0 && (
        <p className="mt-1">
          <span className="text-soft">Working patients (used to tune the tool): </span>
          {links(working)}
        </p>
      )}
      {live.length > 0 && (
        <p className="mt-1">
          <span className="text-soft">Live runs on this laptop: </span>
          {links(live.map((p) => p.patient_id))}
        </p>
      )}
    </div>
  );
}

// Shown above a live record (T58), so no one mistakes it for the saved demo run.
function LiveNote({ run }: { run: LiveRun }) {
  const made = new Date(run.made_at);
  const when = isNaN(made.getTime()) ? run.made_at : made.toLocaleString("en-GB");
  return (
    <Card className="border-2 border-ink">
      <p className="font-medium">Live run on this laptop.</p>
      <p className="mt-1">
        Read just now by {run.model} at {when}, from these files: {run.source_files.join(", ")}. Each record
        went through the same steps as the tested tool: read by Claude, every fact checked against the
        record&rsquo;s own words, then merged with the six rules.
      </p>
      <p className="mt-1 text-sm">
        Tool: {run.tool}. Run {run.run_id}. This record stays on this laptop; the public link only replays a
        saved run.
      </p>
    </Card>
  );
}

// The patient shown when the address has no ID (T68 item 2).
const DEFAULT_ID = SAMPLE_IDS.includes("D001") ? "D001" : (SAMPLE_IDS[0] ?? "");

// The three-way switch (T27, T68 item 21). Links, so it works without JavaScript and the
// address says which view is showing. The current choice is marked in words and with a
// solid fill, not by colour alone.
function ViewSwitch({ id, view }: { id: string; view: PageView }) {
  const options: { value: PageView; label: string; full: string }[] = [
    { value: "handover", label: "Handover", full: "Handover (our tool)" },
    { value: "baseline", label: "Baseline", full: "Baseline (keyword search)" },
    { value: "compare", label: "Compare", full: "Compare side by side" },
  ];
  return (
    <nav aria-label="Choose which record to show">
      <ul className="inline-flex flex-wrap gap-1 rounded-full bg-white p-1.5">
        {options.map((o) => {
          const current = o.value === view;
          return (
            <li key={o.value}>
              <Link
                href={href(id, { view: o.value })}
                aria-current={current ? "page" : undefined}
                title={o.full}
                className={`inline-block rounded-full px-4 py-2 ${current ? "bg-rail text-white font-medium" : "hover:bg-mint"}`}
              >
                {o.label}
                <span className="sr-only">{o.full.slice(o.label.length)}{current && " (showing now)"}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

// The top row: the patient box, the sample patients behind one tap, and the view switch.
function TopBar({ id, view }: { id: string; view: PageView }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      {/* A plain GET form: submitting it puts the ID in the address. */}
      <form action="/" method="get" className="w-full sm:w-auto sm:flex-1 sm:max-w-sm">
        <div className="flex items-center gap-2 rounded-full bg-white p-1.5 pl-5">
          <label htmlFor="id" className="text-sm text-soft whitespace-nowrap">
            Patient ID
          </label>
          <input
            id="id"
            name="id"
            type="text"
            defaultValue={id}
            placeholder="e.g. D001"
            autoComplete="off"
            className="min-w-0 flex-1 bg-transparent py-2 font-medium outline-none"
          />
          {view !== "handover" && <input type="hidden" name="view" value={view} />}
          <button type="submit" className="rounded-full bg-rail px-5 py-2 text-white font-medium">
            Show record
          </button>
        </div>
        <details className="mt-2 px-5 text-sm">
          <summary className="underline underline-offset-2">Sample patients</summary>
          <SampleIds />
        </details>
      </form>
      {id && <ViewSwitch id={id} view={view} />}
    </div>
  );
}

// A message box for the empty and failed states.
function Notice({ title, children, strong = false }: { title: string; children: React.ReactNode; strong?: boolean }) {
  return (
    <Card role="alert" className={strong ? "border-4 border-alert" : ""}>
      <p className="font-medium">{title}</p>
      <div className="mt-1">{children}</div>
    </Card>
  );
}

// What the baseline is, shown above the baseline record so no one mistakes it for the tool's output.
function BaselineNote() {
  return (
    <Card className="border-2 border-ink">
      <p className="font-medium">This is the baseline, not our tool.</p>
      <p className="mt-1">
        A simple keyword search read each hospital record and every line it found is listed, with no
        merging: no checking against the source, no conflict warnings, and no rule for which hospital
        is most recent. It is shown so you can compare it with the Handover record.
      </p>
    </Card>
  );
}

// A titled group of full fact cards (baseline view); renders nothing when empty.
function Section({ title, facts }: { title: string; facts: Fact[] }) {
  if (facts.length === 0) return null;
  return (
    <section>
      <h2 className="text-xl font-medium mb-2">{title}</h2>
      <FactList facts={facts} foldQuotes />
    </section>
  );
}

// A white card holding short fact lines (Handover view).
// inline: also show the chosen line's source under it on a phone (only once a line has been tapped).
function RowCard({ title, facts, id, selected, empty, showStatus = true, inline = false }: { title: string; facts: Fact[]; id: string; selected?: string; empty?: string; showStatus?: boolean; inline?: boolean }) {
  if (facts.length === 0 && !empty) return null;
  return (
    <Card>
      <h2 className="text-lg font-medium mb-1">{title}</h2>
      {facts.length === 0 ? (
        <p className="px-4 py-2 text-soft">{empty}</p>
      ) : (
        <ul className="flex flex-col gap-1 -mx-2">
          {facts.map((f) => (
            <FactRow key={f.fact_id} fact={f} href={href(id, { fact: f.fact_id })} selected={f.fact_id === selected} showStatus={showStatus}>
              {inline && <SourcePanel fact={f} headingId="source-inline" />}
            </FactRow>
          ))}
        </ul>
      )}
    </Card>
  );
}

// The words for a group of facts where hospitals disagree, e.g. "Penicillin allergy".
function conflictTitle(group: Fact[]): string {
  const names = [...new Set(group.filter((f) => f.name && f.status !== "none_recorded").map((f) => factName(f)))];
  const type = group[0].type;
  if (names.length === 0) return type === "allergy" ? "Allergies" : type === "medicine" ? "Medicines" : type === "diagnosis" ? "Diagnoses" : "Operations";
  return `${joinWords(names)}${type === "allergy" ? " allergy" : ""}`;
}

// The patient's label under the ID in the right-hand panel.
function patientKind(id: string): string {
  if (liveRun(id)) return "Live run on this laptop";
  return id.startsWith("D") ? "Demo patient" : "Working patient, used to tune the tool";
}

// The right-hand panel of the Handover view: who the patient is, the records, the source
// of the chosen fact, and the double-check.
function Aside({ id, facts, picked, omission }: { id: string; facts: Fact[]; picked: Fact | null; omission: React.ReactNode }) {
  const lines = bannerLines(facts);
  const entries = hospitalEntries(facts);
  // The most recent date in the record, so its hospital can be marked.
  const newest = entries.reduce<string | null>((a, e) => (e.latest !== null && (a === null || e.latest > a) ? e.latest : a), null);
  return (
    <>
      <div className="flex items-center gap-3">
        <span aria-hidden="true" className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-mint text-rail">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <circle cx="12" cy="8" r="4" />
            <path d="M4 21c0-4 4-6 8-6s8 2 8 6" />
          </svg>
        </span>
        <div>
          <p className="text-lg font-medium">Patient {id}</p>
          <p className="text-sm text-soft">{patientKind(id)}</p>
        </div>
      </div>

      <dl className="grid grid-cols-3 divide-x divide-sage">
        <div>
          <dt className="text-sm text-soft">Hospitals</dt>
          <dd className="text-xl font-medium">{entries.length}</dd>
        </div>
        <div className="pl-3">
          <dt className="text-sm text-soft">Facts</dt>
          <dd className="text-xl font-medium">{facts.length}</dd>
        </div>
        <div className="pl-3">
          <dt className="text-sm text-soft">To check</dt>
          <dd className={`text-xl font-medium ${lines.length > 0 ? "text-alert-ink" : ""}`}>
            {lines.length > 0 ? (
              <Tip
                tip={
                  <>
                    {lines.map((l) => (
                      <span key={l.key} className="block mb-1 last:mb-0">
                        {l.text}
                      </span>
                    ))}
                  </>
                }
              >
                {lines.length}
              </Tip>
            ) : (
              0
            )}
          </dd>
        </div>
      </dl>

      {entries.length > 0 && (
        <section aria-labelledby="entries-heading">
          <h2 id="entries-heading" className="text-lg font-medium">
            Latest entry from each hospital
          </h2>
          <ul className="mt-2 flex gap-2">
            {entries.map((e) => (
              <li key={e.hospital} className="flex-1">
                <Tip className="w-full" tip={`${e.facts} of the ${facts.length} facts come from Hospital ${e.hospital}`}>
                  <span className={`flex w-full flex-col items-center rounded-2xl px-1 py-2 text-center ${e.latest !== null && e.latest === newest ? "bg-rail text-white" : "bg-mint"}`}>
                    <span className="text-sm">
                      <span className="sr-only">Hospital </span>
                      {e.hospital}
                    </span>
                    <span className="text-sm font-medium">{formatDate(e.latest)}</span>
                    {e.latest !== null && e.latest === newest && <span className="sr-only"> (most recent)</span>}
                  </span>
                </Tip>
              </li>
            ))}
          </ul>
          <Link href={href(id, { show: "timeline" })} className="mt-2 inline-block text-sm font-medium underline underline-offset-2">
            See allergies and medicines over time
          </Link>
        </section>
      )}

      {/* On a phone or tablet the source shows under the tapped line instead (FactRow). */}
      {picked ? (
        <div className="hidden xl:block">
          <SourcePanel fact={picked} />
        </div>
      ) : (
        <p className="rounded-2xl bg-mint px-4 py-3 text-soft">Tap a line to see where it came from.</p>
      )}

      {omission}
    </>
  );
}

// Looks up the ID and shows the record, or the right message when there is none.
async function Screen({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const typed = one(sp.id);
  const pageView = parsePageView(sp.view);
  // Which file the single view reads (Compare reads both, below).
  const view: View = pageView === "compare" ? "handover" : pageView;

  // T68 item 2: with no ID in the address, open the demo patient so the first
  // screen shows a record. If D001 is ever not published, use the first sample ID.
  const id = typed || DEFAULT_ID;
  if (!id) {
    return (
      <Page>
        <TopBar id="" view="handover" />
        <Card>Enter a patient ID above to see the merged record.</Card>
      </Page>
    );
  }

  const load = await loadRecordState(id, view);

  // T68 item 21: Compare view needs both records; if the baseline is missing, say so.
  if (pageView === "compare" && load.state === "ok") {
    const base = await loadRecordState(id, "baseline");
    return (
      <Page>
        <TopBar id={load.record.patient_id} view={pageView} />
        <h1 className="text-2xl font-medium">
          Patient {load.record.patient_id}: Handover and baseline side by side
        </h1>
        {base.state === "ok" ? (
          <CompareView handover={load.record} baseline={base.record} />
        ) : (
          <Notice title={`No baseline record to compare for “${id}”.`}>
            Switch back to Handover to see this patient&rsquo;s merged record.
          </Notice>
        )}
      </Page>
    );
  }

  // A known patient with no baseline file: keep the switch so the doctor can go back.
  if (view === "baseline" && load.state === "missing" && isKnownId(id)) {
    return (
      <Page>
        <TopBar id={id} view={view} />
        <Notice title={`No baseline record for “${id}”.`}>Switch back to Handover to see this patient&rsquo;s merged record.</Notice>
      </Page>
    );
  }

  // Failed state: the patient is listed but the file could not be read.
  if (load.state === "failed") {
    return (
      <Page>
        <TopBar id={id} view={view} />
        <Notice strong title={`The record for “${id}” could not be loaded.`}>
          The file is damaged, so nothing is shown rather than part of the record.
        </Notice>
      </Page>
    );
  }

  if (load.state === "missing") {
    return (
      <Page>
        <TopBar id={id} view="handover" />
        <Notice title={`No record found for “${id}”.`}>
          <p>There is no published patient with that ID. Try one of these:</p>
          <SampleIds />
        </Notice>
      </Page>
    );
  }

  const record = load.record;
  const facts = record.facts;
  const pid = record.patient_id;

  // Baseline view: every line the keyword search found, as full cards (unchanged from T68).
  if (view === "baseline") {
    const { sections } = splitSections(facts, "baseline");
    const handover = await loadRecordState(pid, "handover");
    return (
      <Page>
        <TopBar id={pid} view={view} />
        <BaselineNote />
        {handover.state === "ok" && <BaselineSummary handover={handover.record} baseline={record} />}
        <div>
          <h1 className="text-2xl font-medium">Patient {pid}: baseline</h1>
          <p className="text-sm text-soft">
            Every line the keyword search found in {record.built_from.length} hospital records: {facts.length} entries.
          </p>
        </div>
        {sections.map((sec) => (
          <Section key={sec.title} title={sec.title} facts={sec.facts} />
        ))}
      </Page>
    );
  }

  // Handover view.
  const { sections, olderMeds } = splitSections(facts, "handover");
  const [allergies, current, stopped, otherMeds, diagnoses, operations] = sections.map((s) => s.facts.filter((f) => !f.conflict_group));
  const lines = bannerLines(facts);
  // The groups of facts where hospitals disagree, in the order they appear.
  const groups = [...new Set(facts.map((f) => f.conflict_group).filter((g): g is string => Boolean(g)))];
  // Word-search hint (T64), only from the same run as the record.
  const omissionLoad = await loadOmission(pid, record.run_id);
  const omission = <OmissionBox load={omissionLoad} />;
  const live = liveRun(pid);

  // Which fact's source the right-hand panel shows: the one in the address, or else the
  // first line with a warning, or else the first current medicine.
  const wanted = one(sp.fact);
  // True once a line has been tapped (the address names a fact).
  const tapped = facts.some((f) => f.fact_id === wanted);
  const picked =
    facts.find((f) => f.fact_id === wanted) ??
    facts.find((f) => !f.conflict_group && f.flags.length > 0 && (f.type === "allergy" || f.type === "medicine")) ??
    current[0] ??
    facts.find((f) => !f.conflict_group) ??
    null;
  const aside = <Aside id={pid} facts={facts} picked={picked} omission={omission} />;
  const show = one(sp.show);
  const back = (
    <Link href={href(pid)} className="self-start rounded-full bg-white px-5 py-2 font-medium text-rail-ink">
      Back to patient {pid}
    </Link>
  );

  // "Over time" view.
  if (show === "timeline") {
    return (
      <Page aside={aside} asideLabel="Patient and source">
        {back}
        <div>
          <h1 className="text-2xl font-medium">Patient {pid}: allergies and medicines over time</h1>
          <p className="text-soft">Oldest first. Orange marks a recorded allergy or a stopped medicine.</p>
        </div>
        <TimelineView facts={facts} />
      </Page>
    );
  }

  // "See both records" view for one disagreement.
  const shownGroup = groups.find((g) => show === `conflict-${g}`);
  if (shownGroup) {
    const group = facts.filter((f) => f.conflict_group === shownGroup);
    return (
      <Page aside={aside} asideLabel="Patient and source">
        {back}
        <div>
          <h1 className="text-2xl font-medium">{conflictTitle(group)}: hospitals disagree</h1>
          <p className="text-soft">Both records are shown. The tool does not pick one.</p>
        </div>
        <ConflictView facts={group} />
      </Page>
    );
  }

  return (
    <Page aside={aside} asideLabel="Patient and source">
      <TopBar id={pid} view={view} />
      <h1 className="sr-only">Patient {pid}: merged record</h1>
      {live && <LiveNote run={live} />}

      {/* Each disagreement between hospitals gets the biggest card on the screen. */}
      {groups.map((g) => {
        const group = facts.filter((f) => f.conflict_group === g);
        const line = lines.find((l) => l.key === `conflict-${g}`);
        return (
          <Card key={g} id={`conflict-${g}`} className="scroll-mt-4 flex flex-wrap items-center justify-between gap-6">
            <div className="flex-1 basis-72">
              <h2 className="text-2xl font-medium leading-tight">{conflictTitle(group)}: hospitals disagree</h2>
              <p className="mt-2 text-soft">{line ? line.text.slice(line.text.indexOf(": ") + 2) : "Two hospital records say different things."}</p>
              <Link href={href(pid, { show: `conflict-${g}` })} className="mt-3 inline-block font-medium underline underline-offset-2">
                See both records
              </Link>
            </div>
            {/* A picture of the two sides: orange for the side that records something. */}
            <div aria-hidden="true" className="hidden md:flex items-end justify-center gap-3 rounded-t-full bg-leaf px-10 pt-8 pb-4">
              {group.flatMap((f) => [...new Set(f.sources.map((s) => s.hospital))].map((h) => <HospitalDot key={`${f.fact_id}-${h}`} letter={h} alert={recordsRisk(f)} size={recordsRisk(f) ? "h-16 w-16 text-2xl" : "h-12 w-12 text-lg"} />))}
            </div>
          </Card>
        );
      })}

      {/* Allergies: always said in words, even when no record mentions them. */}
      {(allergies.length > 0 || sections[0].facts.length === 0) && (
        <RowCard
          title="Allergies"
          facts={allergies}
          id={pid}
          selected={picked?.fact_id}
          inline={tapped}
          empty="No line about allergies was found in these records. That is not the same as no known allergies."
        />
      )}

      <RowCard title="Current medicines" facts={current} id={pid} selected={picked?.fact_id} inline={tapped} showStatus={false} empty="No current medicines are listed in these records." />

      <div className="grid gap-5 md:grid-cols-2">
        {/* T68 item 19: stopped medicines straight under current ones, with a plain warning. */}
        {stopped.map((f) => (
          <Link
            key={f.fact_id}
            id={`fact-${f.fact_id}`}
            href={href(pid, { fact: f.fact_id })}
            scroll={false}
            className={`scroll-mt-4 flex flex-col gap-1 rounded-3xl bg-alert p-6 text-white ${f.fact_id === picked?.fact_id ? "ring-4 ring-ink" : ""}`}
          >
            <span className="font-normal">Stopped: do not continue without checking</span>
            <span className="mt-auto pt-6 text-4xl font-medium leading-tight break-words">{factName(f)}</span>
            <span className="font-normal">
              since {formatDate(f.date)}, Hospital {f.hospital}
            </span>
          </Link>
        ))}
        {/* The chosen stopped medicine's source, under its card on a phone or tablet. */}
        {stopped
          .filter((f) => tapped && f.fact_id === picked?.fact_id)
          .map((f) => (
            <div key={`${f.fact_id}-source`} className="xl:hidden rounded-3xl bg-white p-5">
              <SourcePanel fact={f} headingId="source-inline" />
            </div>
          ))}
        <RowCard title="Other medicines (planned, or none recorded)" facts={otherMeds} id={pid} selected={picked?.fact_id} inline={tapped} />
        <RowCard title="Diagnoses" facts={diagnoses} id={pid} selected={picked?.fact_id} inline={tapped} />
        <RowCard title="Operations" facts={operations} id={pid} selected={picked?.fact_id} inline={tapped} />
      </div>

      <OlderRecordNote facts={olderMeds} />
    </Page>
  );
}

export default function Home({ searchParams }: { searchParams: SearchParams }) {
  // The disclaimer is in components/Page.tsx, so every tab shows it.
  return (
    <Suspense
      fallback={
        <Page>
          <p>Loading…</p>
        </Page>
      }
    >
      <Screen searchParams={searchParams} />
    </Suspense>
  );
}
