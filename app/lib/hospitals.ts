// The three hospitals' names (T81). The records and the merged record use the letters A, B
// and C; a doctor reads names, so the app shows the name wherever a letter used to be.
// The names are the ones in shared/hospital_formats.md, and all three are made up.
// Display only: no record, score or saved file is changed.
const HOSPITALS: Record<string, { short: string; full: string }> = {
  A: { short: "Northfield", full: "Northfield General Hospital" },
  B: { short: "Riverside", full: "Riverside Community Hospital" },
  C: { short: "Seri Bayu", full: "Seri Bayu Medical Centre" },
};

// The short name for tables and sentences ("Northfield"). An unknown letter keeps its letter.
export function hospitalShort(letter: string): string {
  return HOSPITALS[letter]?.short ?? `Hospital ${letter}`;
}

// The full name for the source panel and hover text ("Northfield General Hospital").
export function hospitalFull(letter: string): string {
  return HOSPITALS[letter]?.full ?? `Hospital ${letter}`;
}
