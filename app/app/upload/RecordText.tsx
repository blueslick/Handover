// A hospital record shown in its own shape (T68 item 28), so the three formats look
// different on screen: a table file drawn as a table, a letter as ordinary text, and
// anything else (the medication sheet) in a fixed-width font, as it was typed.
// The text itself is never changed; the table is only the same cells laid out in rows.

// Splits one CSV line into cells, keeping commas inside "quoted, cells".
function splitCsvLine(line: string): string[] {
  const cells: string[] = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (quoted && line[i + 1] === '"') {
        cell += '"';
        i++;
      } else quoted = !quoted;
    } else if (ch === "," && !quoted) {
      cells.push(cell);
      cell = "";
    } else cell += ch;
  }
  cells.push(cell);
  return cells;
}

const box = "mt-2 max-h-72 overflow-auto rounded-2xl bg-mint p-3";

export default function RecordText({ text, file, format }: { text: string; file: string; format: string }) {
  const lower = `${file} ${format}`.toLowerCase();

  // Table file: header row and one row per line.
  if (file.toLowerCase().endsWith(".csv")) {
    const [head, ...rows] = text.split(/\r?\n/).filter((l) => l.trim() !== "").map(splitCsvLine);
    return (
      <div className={box}>
        <table className="text-xs border-collapse">
          <caption className="sr-only">The hospital&rsquo;s table file, one row per line</caption>
          <thead>
            <tr>
              {head?.map((c, i) => (
                <th key={i} scope="col" className="border border-sage bg-leaf px-1 py-0.5 text-left font-medium">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {r.map((c, j) => (
                  <td key={j} className="border border-sage px-1 py-0.5 align-top whitespace-nowrap">
                    {c}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  // A letter: ordinary text, line breaks kept.
  if (lower.includes("letter")) {
    return <div className={`${box} text-sm whitespace-pre-wrap leading-relaxed`}>{text}</div>;
  }

  // Anything else (the medication sheet): fixed-width, exactly as typed.
  return <pre className={`${box} text-xs font-mono whitespace-pre overflow-x-auto`}>{text}</pre>;
}
