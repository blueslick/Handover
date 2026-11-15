"use client";
// The tabs on every page (T75): a green rail down the left on a laptop, a green bar across
// the top on a phone. The current tab is marked in words (for screen readers) and with a
// white pill, not by colour alone. Add a tab here when its page exists.
import Link from "next/link";
import { usePathname } from "next/navigation";

// The small picture above each tab's name.
function Icon({ name }: { name: "records" | "doctor" | "tests" }) {
  const common = {
    width: 24,
    height: 24,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };
  if (name === "records")
    return (
      <svg {...common}>
        <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
        <path d="M14 3v5h5" />
      </svg>
    );
  if (name === "doctor")
    return (
      <svg {...common}>
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21c0-4 4-6 8-6s8 2 8 6" />
      </svg>
    );
  return (
    <svg {...common}>
      <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
    </svg>
  );
}

const TABS = [
  // T68 item 24: nothing can be uploaded here, so the tab says it is a replay.
  { href: "/upload", label: "Hospital records (replay)", short: "Records replay", icon: "records" as const },
  { href: "/", label: "Doctor screen", short: "Doctor screen", icon: "doctor" as const },
  { href: "/how-we-tested", label: "How we tested", short: "How we tested", icon: "tests" as const },
];

export default function TabNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Tabs"
      className="shrink-0 flex items-center gap-2 px-3 py-2 lg:w-28 lg:flex-col lg:px-0 lg:py-8"
    >
      {/* The app's name and mark. */}
      <div className="flex items-center gap-2 text-white lg:flex-col lg:gap-1 lg:mb-8">
        <svg width="28" height="28" viewBox="0 0 36 36" aria-hidden="true">
          <rect x="13" y="3" width="10" height="30" rx="3" fill="#fff" />
          <rect x="3" y="13" width="30" height="10" rx="3" fill="#fff" />
        </svg>
        <span className="font-medium text-sm">Handover</span>
      </div>
      <ul className="flex flex-1 justify-end gap-1 lg:flex-none lg:flex-col lg:gap-2">
        {TABS.map((tab) => {
          const current = tab.href === "/" ? pathname === "/" : pathname.startsWith(tab.href);
          return (
            <li key={tab.href}>
              <Link
                href={tab.href}
                aria-current={current ? "page" : undefined}
                aria-label={tab.label}
                title={tab.label}
                className={`flex flex-col items-center gap-1 rounded-2xl px-2 py-2 text-center text-xs leading-tight lg:w-24 lg:py-3 ${
                  current ? "bg-white text-rail-ink font-medium" : "text-white hover:bg-white/15"
                }`}
              >
                <Icon name={tab.icon} />
                <span className="max-w-[5.5rem]">{tab.short}</span>
                {current && <span className="sr-only"> (current tab)</span>}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
