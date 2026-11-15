// One hospital record exactly as written (T81). It is raw record text, so it is shown in
// the fixed-width font and nothing in it is changed. When the tool's reading is showing,
// the words each fact came from are highlighted, so the eye can match the two sides.
// Each highlighted piece is a fact's exact quote; joining the pieces gives the text back.
export default function RecordText({ text, quotes }: { text: string; quotes: string[] }) {
  // Find every quote in the text, longest first so a short quote cannot split a long one.
  const spans: { start: number; end: number }[] = [];
  for (const q of [...new Set(quotes)].filter((x) => x.trim().length > 0).sort((a, b) => b.length - a.length)) {
    let from = 0;
    for (;;) {
      const at = text.indexOf(q, from);
      if (at < 0) break;
      if (!spans.some((s) => at < s.end && at + q.length > s.start)) spans.push({ start: at, end: at + q.length });
      from = at + q.length;
    }
  }
  spans.sort((a, b) => a.start - b.start);
  const pieces: { text: string; hit: boolean }[] = [];
  let last = 0;
  for (const s of spans) {
    if (s.start > last) pieces.push({ text: text.slice(last, s.start), hit: false });
    pieces.push({ text: text.slice(s.start, s.end), hit: true });
    last = s.end;
  }
  if (last < text.length) pieces.push({ text: text.slice(last), hit: false });
  return (
    <pre className="max-h-[32rem] overflow-auto rounded-ctl border border-line bg-panel p-3 font-mono text-xs break-words whitespace-pre-wrap">
      {pieces.map((p, i) =>
        p.hit ? (
          <mark key={i} className="rounded-sm bg-accent-tint text-ink">
            {p.text}
          </mark>
        ) : (
          <span key={i}>{p.text}</span>
        ),
      )}
    </pre>
  );
}
