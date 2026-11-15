// "Double-check" box on the doctor screen (T64; renamed in T68 item 20, was "Possibly missed"). Shows the omission check's flags:
// medicine or allergy names a plain word search found in a hospital record that the
// tool did not list. It is a hint to look at the record, never a confirmed fact, so it
// sits in its own box below the record and is not counted in the warning banner.
import type { OmissionLoad } from "@/lib/omission";
import { capitalise } from "@/lib/names";

export default function OmissionBox({ load }: { load: OmissionLoad }) {
  // No check saved for this patient: say nothing rather than suggest it found nothing.
  if (load.state === "missing") return null;

  return (
    <section aria-labelledby="omission-heading" className="rounded-2xl bg-mint px-4 py-3">
      {/* T75: folded to one line in the right-hand panel; the explanation opens on a tap. */}
      <h2 id="omission-heading" className="font-medium">
        Double-check: word search
      </h2>
      <details className="text-sm">
        <summary className="underline underline-offset-2">What is this?</summary>
        <p className="mt-1">
          A simple word search looked for medicine and allergy names in each hospital record and lists any the tool
          did not include in the record. These are hints to check the original record, not confirmed facts.
        </p>
      </details>

      {load.state === "failed" ? (
        <p role="alert" className="mt-2 font-medium">
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
  const checked = records.map((r) => r.hospital).join(", ");

  return (
    <>
      {flagged.length === 0 ? (
        <p className="mt-2">
          Nothing found: every medicine and allergy name the word search found in Hospital{records.length > 1 ? "s" : ""}{" "}
          {checked} is already in the record.
        </p>
      ) : (
        <ul className="mt-3 flex flex-col gap-3">
          {flagged.flatMap((r) =>
            r.flags.map((f) => (
              <li key={`${r.hospital}-${f.generic}`} className="rounded-2xl bg-white p-3">
                <p className="font-medium">
                  {capitalise(f.generic)}
                  {f.terms_as_written.length > 0 &&
                    f.terms_as_written.some((t) => t.toLowerCase() !== f.generic.toLowerCase()) && (
                      <span className="font-normal"> (written as {f.terms_as_written.join(", ")})</span>
                    )}
                </p>
                <p className="text-sm">Possibly missed, found in Hospital {r.hospital}:</p>
                <ul className="mt-1 text-sm">
                  {f.lines.map((l) => (
                    <li key={l.line}>
                      Line {l.line}: <q className="italic">{l.text}</q>
                    </li>
                  ))}
                </ul>
              </li>
            )),
          )}
        </ul>
      )}
      {not_checked.length > 0 && (
        <p className="mt-2 text-sm">Not checked: Hospital {not_checked.join(", ")} (no saved reading).</p>
      )}
    </>
  );
}
