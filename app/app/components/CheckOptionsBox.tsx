// "Who can confirm this" (T80, renamed and folded in T81). Shown with every warning, so the
// doctor is not left with a warning and nothing else: what the merged record did with the
// fact, then the options for checking it (the patient, the medicine's box, and each
// hospital whose record mentions it, with what that record says and the hospital's
// contact). The wording is built in lib/checkOptions.ts.
// Options only: no order, no recommendation, no winner between records, nothing about
// what to prescribe. The hospital contacts are examples (the hospitals are made up), and
// the box says so once.
import { hospitalContact } from "@/lib/hospitalContacts";
import type { CheckPlan } from "@/lib/checkOptions";

// compact: in the narrow right-hand panel the box is folded until tapped, and its heading
// names the warning. open: on the "See both records" page it starts open.
// idPrefix keeps ids apart when the same box is on the page twice (the source panel shows
// in the right-hand panel on a laptop and under the chosen row on a phone).
export default function CheckOptionsBox({ plan, compact = false, open = false, idPrefix = "check" }: { plan: CheckPlan; compact?: boolean; open?: boolean; idPrefix?: string }) {
  const headingId = `${idPrefix}-${plan.key}`;
  return (
    <details open={open} className="border-t border-line pt-2">
      <summary id={headingId} className="font-semibold">
        Who can confirm this{compact && <span className="font-normal text-quiet">: {plan.title.toLowerCase()}</span>}
      </summary>
      <div className="mt-2 flex flex-col gap-2">
        <p>{plan.shows}</p>
        <ul className="flex list-disc flex-col gap-1.5 pl-5">
          {plan.options.map((o) => {
            const contact = o.hospital ? hospitalContact(o.hospital) : null;
            return (
              <li key={o.who}>
                <span className="font-medium">{o.who}</span>
                {o.detail && <span className="block">{o.detail}</span>}
                {contact && (
                  <span className="block break-words text-quiet">
                    {contact.office}: {contact.phone}, {contact.email}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
        <p className="text-quiet">The hospitals and contacts are made up. These are options, not recommendations. The doctor decides.</p>
      </div>
    </details>
  );
}
