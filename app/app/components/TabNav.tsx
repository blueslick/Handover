"use client";
// The row of tabs at the top of every page. The current tab is marked in words
// and with a thick underline, not by colour alone. Add a tab here when its page exists.
import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  // T68 item 24: nothing can be uploaded here, so the tab says it is a replay.
  { href: "/upload", label: "Hospital records (replay)" },
  { href: "/", label: "Doctor screen" },
  { href: "/how-we-tested", label: "How we tested" },
];

export default function TabNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Tabs" className="border-b border-zinc-400">
      <ul className="max-w-5xl mx-auto px-4 sm:px-8 flex gap-4">
        {TABS.map((tab) => {
          const current = tab.href === "/" ? pathname === "/" : pathname.startsWith(tab.href);
          return (
            <li key={tab.href}>
              <Link
                href={tab.href}
                aria-current={current ? "page" : undefined}
                className={`inline-block py-3 border-b-4 ${
                  current ? "border-zinc-800 font-semibold" : "border-transparent underline"
                }`}
              >
                {tab.label}
                {current && <span className="sr-only"> (current tab)</span>}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
