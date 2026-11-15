// Banner at the top: the things a doctor must check before relying on the record.
// The lines are built in lib/banner.ts (T68), so the rules are the same for every patient.
import { bannerLines } from "@/lib/banner";
import type { Fact } from "@/lib/types";

export default function WarningBanner({ facts }: { facts: Fact[] }) {
  const lines = bannerLines(facts);
  if (lines.length === 0) return null;

  return (
    <div role="alert" className="rounded-box border border-warn-line bg-warn-bg p-3">
      <h2 className="text-base font-semibold">Check first</h2>
      <ul className="mt-2 list-disc pl-5 flex flex-col gap-1">
        {lines.map((l) => (
          <li key={l.key}>
            {/* T68 item 11: each line jumps to its card. */}
            <a href={`#${l.target}`} className="underline decoration-1 underline-offset-2 hover:decoration-2">
              {l.text}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
