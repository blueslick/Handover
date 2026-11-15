// "Ways to check this" (T80). Shown with every warning, so the doctor is not left with a
// warning and nothing else: what the merged record did with the fact, then the options for
// checking it (the patient, the medicine's box, and each hospital whose record mentions
// it, with what that record says and the hospital's contact). The wording is built in
// lib/checkOptions.ts.
// Options only: no order, no recommendation, no winner between records, nothing about
// what to prescribe. The hospital contacts are examples (the hospitals are made up) and
// are labelled so.
import { hospitalContact } from "@/lib/hospitalContacts";
import type { CheckPlan } from "@/lib/checkOptions";

// compact: for the narrow right-hand panel (smaller text, and the heading names the warning).
// idPrefix keeps ids apart when the same box is on the page twice (the source panel shows
// in the right-hand panel on a laptop and under the tapped line on a phone).
export default function CheckOptionsBox({ plan, compact = false, idPrefix = "check" }: { plan: CheckPlan; compact?: boolean; idPrefix?: string }) {
  const headingId = `${idPrefix}-${plan.key}`;
  return (
    <section aria-labelledby={headingId} className={`rounded-2xl border-2 border-alert bg-white ${compact ? "px-4 py-3 text-sm" : "p-5 sm:p-6"} flex flex-col gap-3`}>
      <h3 id={headingId} className={compact ? "font-medium" : "text-xl font-medium"}>
        Ways to check this{compact && <span className="font-normal text-soft">: {plan.title.toLowerCase()}</span>}
      </h3>

      <div>
        <p className="font-medium">What this record shows</p>
        <p>{plan.shows}</p>
      </div>

      <div>
        <p className="font-medium">Who could confirm it</p>
        <ul className="mt-1 flex list-disc flex-col gap-2 pl-5">
          {plan.options.map((o) => {
            const contact = o.hospital ? hospitalContact(o.hospital) : null;
            return (
              <li key={o.who}>
                <span className="font-medium">{o.who}</span>
                {o.detail && <span className="block">{o.detail}</span>}
                {contact && (
                  <span className="mt-1 block rounded-xl bg-mint px-3 py-2 break-words">
                    {contact.office}: {contact.phone}, {contact.email}{" "}
                    <span className="text-soft">(example contact: this hospital is made up)</span>
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      </div>

      <p className="text-soft">These are options, not recommendations. The doctor decides.</p>
    </section>
  );
}
