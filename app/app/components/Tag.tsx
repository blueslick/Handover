// A small label (T81). Used only for exceptions: an allergy (red), something the doctor
// must check such as a disagreement or a dose change (amber), or a match (green).
// Everything normal is plain text. The colour is never the only signal: the label is a word.
const KINDS = {
  crit: "border-crit bg-crit-bg text-crit",
  warn: "border-warn-line bg-warn-bg text-warn",
  ok: "border-ok bg-ok-bg text-ok",
  plain: "border-line-strong bg-surface text-quiet",
} as const;

// The one warning icon. It appears once per problem, in "Check first" only.
export function WarnIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0">
      <path d="M12 3 2 21h20z" />
      <path d="M12 10v5" />
      <path d="M12 18h.01" />
    </svg>
  );
}

export default function Tag({ kind, icon = false, children }: { kind: keyof typeof KINDS; icon?: boolean; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-ctl border px-1.5 py-px text-xs font-medium whitespace-nowrap ${KINDS[kind]}`}>
      {icon && <WarnIcon />}
      {children}
    </span>
  );
}
