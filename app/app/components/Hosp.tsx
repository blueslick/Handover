// A hospital's short name, with its full name on hover (T81). Used wherever the app used
// to show the letter A, B or C.
import { formatDate } from "@/lib/dates";
import { hospitalFull, hospitalShort } from "@/lib/hospitals";

export default function Hosp({ letter }: { letter: string }) {
  return <span title={hospitalFull(letter)}>{hospitalShort(letter)}</span>;
}

// A fact's sources as plain text, one per line: hospital, then date. No boxes.
export function SourceLines({ sources }: { sources: { hospital: string; date: string }[] }) {
  return (
    <>
      {sources.map((s, i) => (
        <span key={`${s.hospital}-${s.date}-${i}`} className="block whitespace-nowrap">
          <Hosp letter={s.hospital} /> {formatDate(s.date)}
        </span>
      ))}
    </>
  );
}
