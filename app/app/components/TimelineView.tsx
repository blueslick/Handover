// The patient's allergies and medicines in date order (T75, a plain table since T81),
// oldest first. A recorded allergy or a stopped medicine is tinted and says "Check this".
import { timelineEvents } from "@/lib/timeline";
import { formatDate } from "@/lib/dates";
import type { Fact } from "@/lib/types";
import Hosp from "./Hosp";
import { Box, Card } from "./Page";

export default function TimelineView({ facts }: { facts: Fact[] }) {
  const events = timelineEvents(facts);
  if (events.length === 0) {
    return <Card>No allergies or medicines are in this record, so there is nothing to show over time.</Card>;
  }
  return (
    <Box title="Oldest first" id="timeline">
      <table className="dt stack">
        <thead>
          <tr>
            <th scope="col" className="w-[18%]">Date</th>
            <th scope="col" className="w-[20%]">Hospital</th>
            <th scope="col">What the record says</th>
            <th scope="col" className="w-[16%]">Check</th>
          </tr>
        </thead>
        <tbody>
          {events.map((e) => (
            <tr key={e.key} className={e.alert ? "row-warn" : ""}>
              <td className="whitespace-nowrap">{formatDate(e.date)}</td>
              <td><Hosp letter={e.hospital} /></td>
              <td className="font-medium">{e.text}</td>
              <td>{e.alert ? "Check this" : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Box>
  );
}
