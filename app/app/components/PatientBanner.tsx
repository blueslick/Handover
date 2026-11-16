// The patient banner, at the top of every patient screen and pinned there on a laptop (T81): who the patient is
// and their allergies, so neither is ever out of sight.
// Name, date of birth and sex come from lib/patients.ts (read from the hospital records'
// own headers); allergies come from the merged record. When two hospitals disagree about
// an allergy, both are shown: the banner never says "no known allergies" while any record
// lists one (CLAUDE.md: show both, never pick a winner).
import { connection } from "next/server";
import { formatDate, joinWords } from "@/lib/dates";
import { hospitalFull, hospitalShort } from "@/lib/hospitals";
import { statusLabel } from "@/lib/labels";
import { factHospitals, factName } from "@/lib/names";
import { ageOn, patientDetails } from "@/lib/patients";
import { hospitalEntries } from "@/lib/timeline";
import type { Fact } from "@/lib/types";
import Tag from "./Tag";

// One line of the allergy cell, e.g. "Penicillin, skin rash, Northfield".
function AllergyLine({ fact }: { fact: Fact }) {
  const where = joinWords(factHospitals(fact).map(hospitalShort));
  if (fact.status === "none_recorded") {
    return (
      <p>
        {statusLabel(fact)}, {where}
      </p>
    );
  }
  const real = fact.status === "current" || fact.status === "suspected";
  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
      {real ? <Tag kind="crit">{statusLabel(fact)}</Tag> : <span className="text-quiet">{statusLabel(fact)}:</span>}
      <span className="font-semibold">{factName(fact)}</span>
      <span>
        {fact.reaction ? `${fact.reaction}, ` : ""}
        {where}
      </span>
    </p>
  );
}

export default async function PatientBanner({ id, facts }: { id: string; facts: Fact[] }) {
  const who = patientDetails(id);
  // The age is "as of today", so it is worked out when the page is asked for, not when the
  // app was built (otherwise it would be stuck on the build day).
  await connection();
  const age = who ? ageOn(who.dob) : null;
  const entries = hospitalEntries(facts);
  const allergies = facts.filter((f) => f.type === "allergy");
  const disagree = allergies.some((f) => f.conflict_group || f.flags.includes("conflict"));
  // The side that records an allergy first, then "none recorded" lines.
  const ordered = [...allergies.filter((f) => f.status !== "none_recorded"), ...allergies.filter((f) => f.status === "none_recorded")];
  const records = `${entries.length} hospital ${entries.length === 1 ? "record" : "records"}`;
  return (
    <section aria-label="Patient" className="on-accent z-20 flex flex-wrap bg-accent text-white lg:sticky lg:top-[var(--nav-h,0px)]">
      <div className="flex flex-1 flex-wrap items-center gap-x-6 gap-y-1 px-4 py-2 sm:px-6">
        <p className="text-base font-semibold">{who ? `${who.family.toUpperCase()}, ${who.given}` : `Patient ${id}`}</p>
        {who && (
          <p>
            Born {formatDate(who.dob)}
            {age !== null && ` (${age}y)`}
          </p>
        )}
        {who && <p>{who.sex === "F" ? "Female" : who.sex === "M" ? "Male" : who.sex}</p>}
        {who && <p>ID {id}</p>}
        <p title={entries.map((e) => `${hospitalFull(e.hospital)}, latest entry ${formatDate(e.latest)}`).join("; ")}>{records}</p>
      </div>
      <div className="flex w-full flex-col justify-center gap-1 border-b border-line bg-surface px-4 py-2 text-ink sm:px-6 lg:w-auto lg:min-w-[22rem] lg:border-l">
        <p className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-quiet">Allergies</span>
          {disagree && <Tag kind="warn">Hospitals disagree</Tag>}
        </p>
        {ordered.length === 0 ? <p>No allergy line was found in these records.</p> : ordered.map((f) => <AllergyLine key={f.fact_id} fact={f} />)}
      </div>
    </section>
  );
}
