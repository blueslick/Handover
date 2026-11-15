// Banner at the top: the things a doctor must check before relying on the record.
// The lines are built in lib/banner.ts (T68), so the rules are the same for every patient.
import { bannerLines } from "@/lib/banner";
import type { Fact } from "@/lib/types";

export default function WarningBanner({ facts }: { facts: Fact[] }) {
  const lines = bannerLines(facts);
  if (lines.length === 0) return null;

  return (
    <div role="alert" className="border-2 border-alert bg-peach rounded-3xl p-5">
      <h2 className="text-lg font-medium">Warning: check these before relying on this record</h2>
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
