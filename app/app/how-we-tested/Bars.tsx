// The bars every chart on this tab is drawn with (T81): plain boxes, no chart library.
// The full tool is navy, everything else is grey. Each bar has its number written beside
// it, so nothing depends on reading the length or the colour.
// On a phone the label sits above its bar, so nothing scrolls sideways.

// A round number a little above the largest value, so the axis ends on a tidy figure
// (1,312 gives 1,400). All bars in one chart share it, so they can be compared.
export function niceMax(values: number[]): number {
  const top = Math.max(1, ...values);
  const step = Math.pow(10, Math.floor(Math.log10(top / 4)));
  const size = [1, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6, 7.5, 10].map((m) => m * step).find((s) => s * 4 >= top) ?? step * 10;
  return size * 4;
}

export const fmt = (n: number) => n.toLocaleString("en-GB");
export const percent = (part: number, whole: number) => (whole > 0 ? `${((part / whole) * 100).toFixed(1)}%` : "");

// One row: label, bar, number and a short note. parts: the bar's pieces, left to right.
export function BarRow({ label, strong = false, parts, max, value, note, labelWidth = "sm:w-48" }: { label: string; strong?: boolean; parts: { n: number; className: string }[]; max: number; value: string; note: string; labelWidth?: string }) {
  const total = parts.reduce((a, p) => a + p.n, 0);
  return (
    <div className="flex flex-col gap-x-3 py-0.5 sm:flex-row sm:items-center">
      <span className={`shrink-0 ${labelWidth} ${strong ? "font-semibold" : ""}`}>{label}</span>
      <span className="flex min-h-7 min-w-0 flex-1 items-center gap-2 border-l border-line-strong">
        {/* The bar takes up to 60% of the row, so there is always room for the number. */}
        <span className="flex h-4" style={{ width: `${(total / max) * 60}%`, minWidth: "2px" }} aria-hidden="true">
          {parts.filter((p) => p.n > 0 || total === 0).map((p, i) => (
            <span key={i} className={p.className} style={{ width: total > 0 ? `${(p.n / total) * 100}%` : "100%" }} />
          ))}
        </span>
        <span className="whitespace-nowrap">
          <span className="font-semibold">{value}</span> <span className="text-quiet">{note}</span>
        </span>
      </span>
    </div>
  );
}

// The numbers under a chart: 0, a quarter, a half, three quarters and the top of the scale.
export function Axis({ max, labelWidth = "sm:w-48" }: { max: number; labelWidth?: string }) {
  return (
    <div className="hidden gap-x-3 sm:flex" aria-hidden="true">
      <span className={`shrink-0 ${labelWidth}`} />
      <span className="flex-1">
        <span className="flex w-[60%] justify-between border-t border-line-strong pt-0.5 text-xs text-quiet">
          {[0, 1, 2, 3, 4].map((i) => (
            <span key={i}>{fmt((max / 4) * i)}</span>
          ))}
        </span>
      </span>
    </div>
  );
}
