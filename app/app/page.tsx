// Doctor screen. The patient ID comes from the address (/?id=D001).
// Reads JSON from app/data/ only: no model calls, no key.
// T81 (clinical look): the patient banner is pinned at the top, then "Check first", then
// plain tables for allergies, medications, problems and operations. Choosing a row puts
// its source in the right-hand panel (address: &fact=...). "See both" and "Record over
// time" open their own views (address: &show=...). Everything is a plain link, so it
// works without JavaScript and the address says what is showing.
// The Baseline and Compare views are still here (address: &view=...), but they are opened
// from the How we tested tab now, not from this screen.
import Link from "next/link";
import { Suspense } from "react";
import { isKnownId, liveRun, loadRecordState, parsePageView, SAMPLE_IDS, type LiveRun, type PageView, type View } from "@/lib/records";
import type { Fact } from "@/lib/types";
import { loadOmission } from "@/lib/omission";
import { splitSections } from "@/lib/sections";
import { formatDate, joinWords } from "@/lib/dates";
import { bannerLines, checkLabels, conflictAnchor, factAnchor, stillListedAt } from "@/lib/banner";
import { conflictPlan } from "@/lib/checkOptions";
import { FREQUENCY_LABELS, statusLabel } from "@/lib/labels";
import { factName } from "@/lib/names";
import BaselineSummary from "./components/BaselineSummary";
import CheckOptionsBox from "./components/CheckOptionsBox";
import CompareView from "./components/CompareView";
import ConflictView from "./components/ConflictView";
import FactList from "./components/FactList";
import { SourceLines } from "./components/Hosp";
import OlderRecordNote from "./components/OlderRecordNote";
import OmissionBox from "./components/OmissionBox";
import Page, { Box, Card } from "./components/Page";
import PatientBanner from "./components/PatientBanner";
import SourcePanel from "./components/SourcePanel";
import Tag from "./components/Tag";
import TimelineView from "./components/TimelineView";

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

// Links to the sample IDs, on the unknown-ID message (CLAUDE.md: an unknown patient ID
// gets a clear message and the list of sample IDs).
function SampleIds() {
  return (
    <p className="mt-2">
      {SAMPLE_IDS.map((id) => (
        <Link key={id} href={`/?id=${id}`} className="mr-2 inline-block font-medium underline">
          {id}
        </Link>
      ))}
    </p>
  );
}

// Shown above a live record (T58), so no one mistakes it for the saved demo run.
function LiveNote({ run }: { run: LiveRun }) {
  const made = new Date(run.made_at);
  const when = isNaN(made.getTime()) ? run.made_at : made.toLocaleString("en-GB");
  return (
    <Card className="border-ink">
      <p className="font-semibold">Live run on this laptop.</p>
      <p className="mt-1">
        Read just now by {run.model} at {when}, from these files: {run.source_files.join(", ")}. Each record
        went through the same steps as the tested tool: read by Claude, every fact checked against the
        record&rsquo;s own words, then merged with the six rules.
      </p>
      <p className="mt-1 text-xs text-quiet">
        Tool: {run.tool}. Run {run.run_id}. This record stays on this laptop; the public link only replays a
        saved run.
      </p>
    </Card>
  );
}

// The patient shown when the address has no ID (T68 item 2).
const DEFAULT_ID = SAMPLE_IDS.includes("D001") ? "D001" : (SAMPLE_IDS[0] ?? "");

// The thin bar under the patient banner: the two views of the record as tabs, and one
// line saying where the record came from.
function RecordBar({ id, showing }: { id: string; showing: "summary" | "timeline" }) {
  const tab = (label: string, to: string, current: boolean) => (
    <Link href={to} aria-current={current ? "page" : undefined} className={`flex min-h-10 items-center border-b-2 px-3 ${current ? "border-accent font-semibold text-ink" : "border-transparent text-quiet hover:text-ink"}`}>
      {label}
    </Link>
  );
  return (
    <div className="flex flex-wrap items-center gap-x-4 border-b border-line bg-surface px-1 sm:px-3">
      <nav aria-label="Views of this record" className="flex">
        {tab("Summary", href(id), showing === "summary")}
        {tab("Record over time", href(id, { show: "timeline" }), showing === "timeline")}
      </nav>
      <p className="px-3 py-1 text-xs sm:ml-auto">Read from hospital records by AI. Check the source before acting.</p>
    </div>
  );
}

// The bar for the views that leave the summary (baseline, compare, see both): one link back.
function BackBar({ id, label }: { id: string; label: string }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 border-b border-line bg-surface px-4 py-2 sm:px-6">
      <Link href={href(id)} className="font-medium underline underline-offset-2">
        Back to the record
      </Link>
      <p className="text-xs text-quiet sm:ml-auto">{label}</p>
    </div>
  );
}

// A message box for the empty and failed states.
function Notice({ title, children, strong = false }: { title: string; children: React.ReactNode; strong?: boolean }) {
  return (
    <Card role="alert" className={strong ? "border-2 border-warn-line" : ""}>
      <p className="font-semibold">{title}</p>
      <div className="mt-1">{children}</div>
    </Card>
  );
}

// What the baseline is, shown above the baseline record so no one mistakes it for the tool's output.
function BaselineNote() {
  return (
    <Card className="border-ink">
      <p className="font-semibold">This is the baseline, not our tool.</p>
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
      <h2 className="mb-2 text-base font-semibold">{title}</h2>
      <FactList facts={facts} foldQuotes />
    </section>
  );
}

// What every table needs to know about the page it is on.
interface TableProps {
  id: string;
  // The fact whose source is showing, if any.
  selected?: string;
  // True once a row has been chosen: on a phone its source then shows under the row.
  tapped: boolean;
}

// The name a fact was written under, when it differs from the generic name shown
// (a brand name such as Glucophage, or another name such as acetaminophen).
function writtenAs(f: Fact): string | null {
  const written = f.name_as_written ?? "";
  return f.status !== "none_recorded" && f.name && written && written.toLowerCase() !== f.name.toLowerCase() ? written : null;
}

// A fact's sources for the Sources column. A stopped medicine also lists the hospital
// whose older record still shows it as current, so both sides are in sight.
function rowSources(f: Fact): { hospital: string; date: string }[] {
  const out = f.sources.map((s) => ({ hospital: s.hospital, date: s.date }));
  for (const h of stillListedAt(f)) {
    const latest = f.history.filter((x) => x.hospital === h && x.status === "current").sort((a, b) => (a.date < b.date ? 1 : -1))[0];
    if (latest) out.push({ hospital: h, date: latest.date });
  }
  return out;
}

// The parts every row shares: its tint and its id (so "Go to row" can find it), the
// Check column's labels, the link in the last column, and the source under the row on a phone.
function rowParts(f: Fact, facts: Fact[], { id, selected, tapped }: TableProps, columns: number) {
  const labels = checkLabels(f);
  const isSelected = f.fact_id === selected;
  // The first row of a group where hospitals disagree carries the group's id.
  const firstOfGroup = f.conflict_group && facts.find((x) => x.conflict_group === f.conflict_group) === f;
  return {
    rowProps: {
      id: firstOfGroup ? conflictAnchor(f.conflict_group!) : factAnchor(f.fact_id),
      className: `scroll-mt-28 ${labels.length > 0 ? "row-warn" : ""} ${isSelected ? "row-sel" : ""}`,
    },
    check: (
      <td>
        {labels.length > 0 && (
          <span className="flex flex-wrap gap-1">
            {labels.map((l) => (
              <Tag key={l} kind="warn">
                {l}
              </Tag>
            ))}
          </span>
        )}
      </td>
    ),
    link: (
      <td className="lnk">
        {f.conflict_group ? (
          <Link href={href(id, { show: `conflict-${f.conflict_group}` })} className="underline underline-offset-2">
            See both<span className="sr-only"> records for {factName(f)}</span>
          </Link>
        ) : (
          <>
            {/* On a phone, tapping again closes the open source (the laptop panel stays). */}
            {isSelected && tapped ? (
              <>
                <Link href={href(id)} scroll={false} aria-current="true" className="underline underline-offset-2 xl:hidden">
                  Hide source<span className="sr-only"> of {factName(f)}</span>
                </Link>
                <Link href={href(id, { fact: f.fact_id })} scroll={false} aria-current="true" className="hidden underline underline-offset-2 xl:inline">
                  Source<span className="sr-only"> of {factName(f)}</span>
                </Link>
              </>
            ) : (
              <Link href={href(id, { fact: f.fact_id })} scroll={false} aria-current={isSelected ? "true" : undefined} className="underline underline-offset-2">
                Source<span className="sr-only"> of {factName(f)}</span>
              </Link>
            )}
          </>
        )}
      </td>
    ),
    // On a phone or tablet the right-hand panel sits far below, so the source shows here.
    inline: isSelected && tapped && (
      <tr key={`${f.fact_id}-source`} className="xl:hidden">
        <td colSpan={columns} className="bg-surface">
          <SourcePanel fact={f} headingId="source-inline" />
          {/* A way to close the source again on a phone. */}
          <p className="mt-3">
            <Link href={href(id)} scroll={false} className="font-medium underline underline-offset-2">
              Hide source
            </Link>
          </p>
        </td>
      </tr>
    ),
  };
}

// Allergies: always said in words, even when no record mentions them.
function AllergyTable({ facts, ...p }: TableProps & { facts: Fact[] }) {
  return (
    <Box title="Allergies" id="allergies">
      {facts.length === 0 ? (
        <p className="px-3 py-2 text-quiet">No line about allergies was found in these records. That is not the same as no known allergies.</p>
      ) : (
        <table className="dt stack">
          <thead>
            <tr>
              <th scope="col" className="w-[24%]">Allergy</th>
              <th scope="col" className="w-[14%]">Reaction</th>
              <th scope="col" className="w-[16%]">Status</th>
              <th scope="col">Sources</th>
              <th scope="col" className="w-[19%]">Check</th>
              <th scope="col" className="lnk"><span className="sr-only">Open</span></th>
            </tr>
          </thead>
          <tbody>
            {facts.flatMap((f) => {
              const r = rowParts(f, facts, p, 6);
              const real = f.status === "current" || f.status === "suspected";
              return [
                <tr key={f.fact_id} {...r.rowProps}>
                  <td className={real ? "font-semibold" : ""}>{factName(f)}</td>
                  <td>{f.reaction ?? ""}</td>
                  <td>{real ? <Tag kind="crit">{statusLabel(f)}</Tag> : f.status === "none_recorded" ? "None recorded" : statusLabel(f)}</td>
                  <td><SourceLines sources={rowSources(f)} /></td>
                  {r.check}
                  {r.link}
                </tr>,
                r.inline,
              ];
            })}
          </tbody>
        </table>
      )}
    </Box>
  );
}

// Medications: current ones first, then planned or "none recorded" lines, then stopped ones.
function MedTable({ facts, ...p }: TableProps & { facts: Fact[] }) {
  return (
    <Box title="Medications" id="meds">
      {facts.length === 0 ? (
        <p className="px-3 py-2 text-quiet">No medicines are listed in these records.</p>
      ) : (
        <table className="dt stack">
          <thead>
            <tr>
              <th scope="col" className="w-[22%]">Medicine</th>
              <th scope="col">Dose</th>
              <th scope="col">Frequency</th>
              <th scope="col">Status</th>
              <th scope="col">Sources</th>
              <th scope="col" className="w-[19%]">Check</th>
              <th scope="col" className="lnk"><span className="sr-only">Open</span></th>
            </tr>
          </thead>
          <tbody>
            {facts.flatMap((f) => {
              const r = rowParts(f, facts, p, 7);
              const written = writtenAs(f);
              return [
                <tr key={f.fact_id} {...r.rowProps}>
                  <td>
                    <span className={f.status === "none_recorded" ? "" : "font-semibold"}>{factName(f)}</span>
                    {written && <span className="text-xs text-quiet"> written as {written}</span>}
                  </td>
                  <td className="whitespace-nowrap">{f.dose ?? ""}</td>
                  <td className="whitespace-nowrap">{f.frequency ? (FREQUENCY_LABELS[f.frequency] ?? f.frequency) : ""}</td>
                  <td className="whitespace-nowrap">{f.status === "stopped" ? `Stopped ${formatDate(f.date)}` : f.status === "none_recorded" ? "None recorded" : statusLabel(f)}</td>
                  <td><SourceLines sources={rowSources(f)} /></td>
                  {r.check}
                  {r.link}
                </tr>,
                r.inline,
              ];
            })}
          </tbody>
        </table>
      )}
    </Box>
  );
}

// Problems (diagnoses) and operations: name, status, sources.
function PlainTable({ title, column, anchor, facts, ...p }: TableProps & { title: string; column: string; anchor: string; facts: Fact[] }) {
  if (facts.length === 0) return null;
  return (
    <Box title={title} id={anchor}>
      <table className="dt stack">
        <thead>
          <tr>
            <th scope="col" className="w-[24%]">{column}</th>
            <th scope="col" className="w-[14%]">Status</th>
            <th scope="col">Sources</th>
            <th scope="col" className="w-[19%]">Check</th>
            <th scope="col" className="lnk"><span className="sr-only">Open</span></th>
          </tr>
        </thead>
        <tbody>
          {facts.flatMap((f) => {
            const r = rowParts(f, facts, p, 5);
            return [
              <tr key={f.fact_id} {...r.rowProps}>
                <td className="font-semibold">{factName(f)}</td>
                <td>{statusLabel(f)}</td>
                <td><SourceLines sources={rowSources(f)} /></td>
                {r.check}
                {r.link}
              </tr>,
              r.inline,
            ];
          })}
        </tbody>
      </table>
    </Box>
  );
}

// The words for a group of facts where hospitals disagree, e.g. "Penicillin allergy".
function conflictTitle(group: Fact[]): string {
  const names = [...new Set(group.filter((f) => f.name && f.status !== "none_recorded").map((f) => factName(f)))];
  const type = group[0].type;
  if (names.length === 0) return type === "allergy" ? "Allergies" : type === "medicine" ? "Medicines" : type === "diagnosis" ? "Diagnoses" : "Operations";
  return `${joinWords(names)}${type === "allergy" ? " allergy" : ""}`;
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
        <Card>Enter a patient ID above to see the merged record.</Card>
      </Page>
    );
  }

  const load = await loadRecordState(id, view);

  // T68 item 21: Compare view needs both records; if the baseline is missing, say so.
  if (pageView === "compare" && load.state === "ok") {
    const base = await loadRecordState(id, "baseline");
    const pid = load.record.patient_id;
    return (
      <Page banner={<PatientBanner id={pid} facts={load.record.facts} />} bar={<BackBar id={pid} label="Handover and the keyword baseline, side by side" />}>
        <h1 className="text-xl font-semibold">Patient {pid}: Handover and baseline side by side</h1>
        {base.state === "ok" ? (
          <CompareView handover={load.record} baseline={base.record} />
        ) : (
          <Notice title={`No baseline record to compare for “${id}”.`}>Go back to the record to see this patient&rsquo;s merged record.</Notice>
        )}
      </Page>
    );
  }

  // A known patient with no baseline file: keep a way back.
  if (view === "baseline" && load.state === "missing" && isKnownId(id)) {
    return (
      <Page bar={<BackBar id={id} label="Keyword baseline" />}>
        <Notice title={`No baseline record for “${id}”.`}>Go back to the record to see this patient&rsquo;s merged record.</Notice>
      </Page>
    );
  }

  // Failed state: the patient is listed but the file could not be read.
  if (load.state === "failed") {
    return (
      <Page>
        <Notice strong title={`The record for “${id}” could not be loaded.`}>
          The file is damaged, so nothing is shown rather than part of the record.
        </Notice>
      </Page>
    );
  }

  if (load.state === "missing") {
    return (
      <Page>
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
      <Page banner={handover.state === "ok" ? <PatientBanner id={pid} facts={handover.record.facts} /> : undefined} bar={<BackBar id={pid} label="Keyword baseline, not our tool" />}>
        <BaselineNote />
        {handover.state === "ok" && <BaselineSummary handover={handover.record} baseline={record} />}
        <div>
          <h1 className="text-xl font-semibold">Patient {pid}: baseline</h1>
          <p className="text-quiet">
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
  const [allergies, current, stopped, otherMeds, diagnoses, operations] = sections.map((s) => s.facts);
  // Stopped medicines sit under current ones (and under planned or "none recorded" lines).
  const meds = [...current, ...otherMeds, ...stopped];
  const lines = bannerLines(facts);
  // The groups of facts where hospitals disagree, in the order they appear.
  const groups = [...new Set(facts.map((f) => f.conflict_group).filter((g): g is string => Boolean(g)))];
  // Word-search hint (T64), only from the same run as the record.
  const omissionLoad = await loadOmission(pid, record.run_id);
  const live = liveRun(pid);

  // Which fact's source the right-hand panel shows: the one in the address, or else the
  // first line with a warning, or else the first current medicine.
  const wanted = one(sp.fact);
  // True once a row has been chosen (the address names a fact).
  const tapped = facts.some((f) => f.fact_id === wanted);
  const picked =
    facts.find((f) => f.fact_id === wanted) ??
    facts.find((f) => !f.conflict_group && f.flags.length > 0 && (f.type === "allergy" || f.type === "medicine")) ??
    current.find((f) => !f.conflict_group) ??
    facts.find((f) => !f.conflict_group) ??
    null;
  const aside = (
    <>
      {/* On a phone or tablet the source shows under the chosen row instead (rowParts). */}
      {picked ? (
        <div className={tapped ? "hidden xl:block" : ""}>
          <SourcePanel fact={picked} />
        </div>
      ) : (
        <p className="text-quiet">Choose a row to see where it came from.</p>
      )}
      <OmissionBox load={omissionLoad} />
    </>
  );
  const banner = <PatientBanner id={pid} facts={facts} />;
  const show = one(sp.show);

  // "Record over time" view.
  if (show === "timeline") {
    return (
      <Page banner={banner} bar={<RecordBar id={pid} showing="timeline" />} aside={aside} asideLabel="Source">
        <div>
          <h1 className="text-xl font-semibold">Allergies and medicines over time</h1>
          <p className="text-quiet">Oldest first. A recorded allergy or a stopped medicine is marked &ldquo;Check this&rdquo;.</p>
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
      <Page banner={banner} bar={<BackBar id={pid} label="Both records are shown. The tool does not pick one." />} aside={aside} asideLabel="Source">
        <h1 className="text-xl font-semibold">{conflictTitle(group)}: hospitals disagree</h1>
        <ConflictView facts={group} />
        {/* T80: the options for checking it, so the doctor is not left with a warning alone. */}
        <CheckOptionsBox plan={conflictPlan(group)} open />
      </Page>
    );
  }

  const table = { id: pid, selected: picked?.fact_id, tapped };
  return (
    <Page banner={banner} bar={<RecordBar id={pid} showing="summary" />} aside={aside} asideLabel="Source">
      <h1 className="sr-only">Patient {pid}: merged record</h1>
      {live && <LiveNote run={live} />}

      {/* What the doctor must look at first: one warning icon and one sentence per problem. */}
      {lines.length > 0 && (
        <Box title="Check first" id="check-first" tone="warn">
          <ul>
            {lines.map((l) => (
              <li key={l.key} className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-line px-3 py-1.5 last:border-b-0">
                <span className="sm:w-40 sm:shrink-0">
                  <Tag kind="warn" icon>
                    {l.label}
                  </Tag>
                </span>
                <span className="min-w-0 flex-1 basis-64">{l.text}</span>
                <a href={`#${l.target}`} className="whitespace-nowrap underline underline-offset-2">
                  Go to row
                </a>
              </li>
            ))}
          </ul>
        </Box>
      )}

      <AllergyTable facts={allergies} {...table} />
      <MedTable facts={meds} {...table} />
      <PlainTable title="Problems" column="Problem" anchor="problems" facts={diagnoses} {...table} />
      <PlainTable title="Operations" column="Operation" anchor="operations" facts={operations} {...table} />

      <OlderRecordNote facts={olderMeds} />
    </Page>
  );
}

export default function Home({ searchParams }: { searchParams: SearchParams }) {
  // The disclaimer is in components/Page.tsx, so every tab shows them.
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
