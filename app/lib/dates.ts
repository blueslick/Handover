// Dates in words for people, e.g. "2021-10-05" -> "5 Oct 2021" (T68).
// Anything that is not a plain YYYY-MM-DD date is shown exactly as stored.
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function formatDate(raw: string | null | undefined): string {
  if (!raw) return "date not recorded";
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw.trim());
  if (!m) return raw;
  const month = MONTHS[Number(m[2]) - 1];
  if (!month) return raw;
  return `${Number(m[3])} ${month} ${m[1]}`;
}

// "A", "A and B", "A, B and C": for sentences such as "Hospitals A, B and C".
export function joinWords(items: string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}
