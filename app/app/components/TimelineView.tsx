// The patient's allergies and medicines in date order (T75), oldest first. Orange marks a
// recorded allergy or a stopped medicine, and those lines also say so in words.
import { timelineEvents } from "@/lib/timeline";
import { formatDate } from "@/lib/dates";
import type { Fact } from "@/lib/types";
import { Card } from "./Page";

export default function TimelineView({ facts }: { facts: Fact[] }) {
  const events = timelineEvents(facts);
  if (events.length === 0) {
    return <Card>No allergies or medicines are in this record, so there is nothing to show over time.</Card>;
  }
  return (
    <Card>
      <ol className="grid gap-x-4 gap-y-6 sm:grid-cols-2 lg:grid-cols-4">
        {events.map((e) => (
          <li key={e.key} className={`border-t-4 pt-3 ${e.alert ? "border-alert" : "border-rail"}`}>
            <p className="text-sm text-soft">
              {formatDate(e.date)}, Hospital {e.hospital}
            </p>
            <p className="text-lg font-medium leading-snug break-words">{e.text}</p>
            {e.alert && <p className="text-sm text-alert-ink">Check this</p>}
          </li>
        ))}
      </ol>
    </Card>
  );
}
