// A small extra shown on hover (T75). It also shows when the item is tapped or reached
// with the Tab key, because a phone has no hover. Only short, nice-to-know extras go in
// here: anything a doctor must see is on the page or one tap away, never hover-only.
// The hover group has its own name ("tip"), so the extra shows only when THIS item is
// hovered, not when a box around it is (Abby's review: every table tip opened at once).
// up: open above the item instead of below it.
export default function Tip({ children, tip, className = "", up = false }: { children: React.ReactNode; tip: React.ReactNode; className?: string; up?: boolean }) {
  return (
    <span tabIndex={0} className={`group/tip relative inline-flex cursor-help ${className}`}>
      {children}
      <span
        role="tooltip"
        className={`pointer-events-none invisible absolute left-1/2 z-20 w-max max-w-[16rem] -translate-x-1/2 rounded-xl bg-ink px-3 py-2 text-left text-xs font-normal leading-snug text-white opacity-0 shadow-lg transition-opacity group-hover/tip:visible group-hover/tip:opacity-100 group-focus/tip:visible group-focus/tip:opacity-100 ${up ? "bottom-full mb-2" : "top-full mt-2"}`}
      >
        {tip}
      </span>
    </span>
  );
}
