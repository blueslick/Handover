// "Double-check" box on the doctor screen (T64; renamed in T68 item 20, was "Possibly missed"). Shows the omission check's flags:
// medicine or allergy names a plain word search found in a hospital record that the
// tool did not list. It is a hint to look at the record, never a confirmed fact, so it
// sits in its own box below the record and is not counted in the warning banner.
import type { OmissionLoad } from "@/lib/omission";
import { joinWords } from "@/lib/dates";
import { hospitalShort } from "@/lib/hospitals";
import { capitalise } from "@/lib/names";

export default function OmissionBox({ load }: { load: OmissionLoad }) {
  // No check saved for this patient: say nothing rather than suggest it found nothing.
  if (load.state === "missing") return null;
  // T81: when the word search found nothing and every record was checked, the box is left
  // out, so the screen carries no line that needs no action. It shows whenever there is a
  // hint, a record that was not checked, or a file that failed to load.
  if (load.state === "ok" && load.omission.not_checked.length === 0 && load.omission.records.every((r) => r.flags.length === 0)) return null;

  return (
    <section aria-labelledby="omission-heading" className="border-t border-line pt-2">
      <h2 id="omission-heading" className="font-semibold">
        Double-check: word search
      </h2>
      <details>
        <summary className="text-quiet">What is this?</summary>
        <p className="mt-1">
          A simple word search looked for medicine and allergy names in each hospital record and lists any the tool
          did not include in the record. These are hints to check the original record, not confirmed facts.
        </p>
      </details>

      {load.state === "failed" ? (
        <p role="alert" className="mt-2 font-semibold">
          The word-search results could not be loaded, so none are shown.
        </p>
      ) : (
        <Results load={load} />
      )}
    </section>
  );
}

function Results({ load }: { load: Extract<OmissionLoad, { state: "ok" }> }) {
  const { records, not_checked } = load.omission;
  const flagged = records.filter((r) => r.flags.length > 0);
  const checked = joinWords(records.map((r) => hospitalShort(r.hospital)));

  return (
    <>
      {flagged.length === 0 ? (
        <p className="mt-2">
          Nothing found: every medicine and allergy name the word search found at {checked} is already in the record.
        </p>
      ) : (
        <ul className="mt-3 flex flex-col gap-3">
          {flagged.flatMap((r) =>
            r.flags.map((f) => (
              <li key={`${r.hospital}-${f.generic}`} className="border-t border-line pt-2">
                <p className="font-semibold">
                  {capitalise(f.generic)}
                  {f.terms_as_written.length > 0 &&
                    f.terms_as_written.some((t) => t.toLowerCase() !== f.generic.toLowerCase()) && (
                      <span className="font-normal"> (written as {f.terms_as_written.join(", ")})</span>
                    )}
                </p>
                <p>Possibly missed, found at {hospitalShort(r.hospital)}:</p>
                <ul className="mt-1">
                  {f.lines.map((l) => (
                    <li key={l.line}>
                      Line {l.line}: <q className="font-mono text-xs">{l.text}</q>
                    </li>
                  ))}
                </ul>
              </li>
            )),
          )}
        </ul>
      )}
      {not_checked.length > 0 && (
        <p className="mt-2">Not checked: {joinWords(not_checked.map(hospitalShort))} (no saved reading).</p>
      )}
    </>
  );
}
