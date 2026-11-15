// A small extra shown on hover (T75). It also shows when the item is tapped or reached
// with the Tab key, because a phone has no hover. Only short, nice-to-know extras go in
// here: anything a doctor must see is on the page or one tap away, never hover-only.
export default function Tip({ children, tip, className = "" }: { children: React.ReactNode; tip: React.ReactNode; className?: string }) {
  return (
    <span tabIndex={0} className={`group relative inline-flex cursor-help ${className}`}>
      {children}
      <span
        role="tooltip"
        className="pointer-events-none invisible absolute left-1/2 top-full z-20 mt-2 w-max max-w-[16rem] -translate-x-1/2 rounded-xl bg-ink px-3 py-2 text-left text-xs font-normal leading-snug text-white opacity-0 shadow-lg transition-opacity group-hover:visible group-hover:opacity-100 group-focus:visible group-focus:opacity-100"
      >
        {tip}
      </span>
    </span>
  );
}
