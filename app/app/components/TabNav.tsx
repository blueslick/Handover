"use client";
// The bar across the top of every page (T81): the app's name, the three tabs, and the
// patient box. The current tab is marked in words (for screen readers) and with a navy
// underline and bold text, not by colour alone. Add a tab here when its page exists.
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense } from "react";

const TABS = [
  // T68 item 24: nothing can be uploaded here, so the tab says it is a replay.
  { href: "/upload", label: "Records replay" },
  { href: "/", label: "Doctor screen" },
  { href: "/how-we-tested", label: "How we tested" },
];

// The patient box. A plain GET form: submitting it puts the ID in the address, so it
// works without JavaScript. It keeps showing the ID that is in the address.
function PatientBox({ demo, working, live }: { demo: string[]; working: string[]; live: string[] }) {
  const pathname = usePathname();
  const params = useSearchParams();
  const current = pathname === "/" ? (params.get("id") ?? demo[0] ?? "") : "";
  const links = (ids: string[]) =>
    ids.map((id) => (
      <Link key={id} href={`/?id=${id}`} className="mr-2 inline-block font-medium underline">
        {id}
      </Link>
    ));
  return (
    <div className="flex flex-wrap items-center gap-2 sm:ml-auto">
      <form action="/" method="get" className="flex items-center gap-2">
        <label htmlFor="id" className="text-quiet">
          Patient ID
        </label>
        <input id="id" name="id" type="text" key={current} defaultValue={current} placeholder="e.g. D001" autoComplete="off" className="h-8 w-24 rounded-ctl border border-line-strong bg-surface px-2" />
        <button type="submit" className="h-8 rounded-ctl border border-accent bg-accent px-3 font-medium text-white">
          Open record
        </button>
      </form>
      {/* T68 item 5: grouped and labelled, so it is clear D001 is the demo patient and the
          P IDs are the working patients the tool was tuned on. */}
      <details className="relative">
        <summary className="list-none underline underline-offset-2 [&::-webkit-details-marker]:hidden">Sample patients</summary>
        <div className="absolute right-0 z-30 mt-1 w-72 rounded-box border border-line bg-surface p-3 text-sm">
          {demo.length > 0 && (
            <p>
              <span className="text-quiet">Demo patient: </span>
              {links(demo)}
            </p>
          )}
          {working.length > 0 && (
            <p className="mt-1">
              <span className="text-quiet">Working patients (used to tune the tool): </span>
              {links(working)}
            </p>
          )}
          {live.length > 0 && (
            <p className="mt-1">
              <span className="text-quiet">Live runs on this laptop: </span>
              {links(live)}
            </p>
          )}
        </div>
      </details>
    </div>
  );
}

export default function TabNav({ demo, working, live }: { demo: string[]; working: string[]; live: string[] }) {
  const pathname = usePathname();
  return (
    <header className="flex flex-wrap items-center gap-x-6 gap-y-1 border-b border-line bg-surface px-4 py-1 sm:px-6 sm:py-0">
      <span className="text-base font-semibold">Handover</span>
      <nav aria-label="Tabs" className="flex self-stretch">
        {TABS.map((tab) => {
          const current = tab.href === "/" ? pathname === "/" : pathname.startsWith(tab.href);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              aria-current={current ? "page" : undefined}
              className={`flex min-h-11 items-center border-b-2 px-3 ${current ? "border-accent font-semibold text-ink" : "border-transparent text-quiet hover:text-ink"}`}
            >
              {tab.label}
              {current && <span className="sr-only"> (current tab)</span>}
            </Link>
          );
        })}
      </nav>
      {/* The patient box reads the address, so it waits for the page to be ready. */}
      <Suspense fallback={null}>
        <PatientBox demo={demo} working={working} live={live} />
      </Suspense>
    </header>
  );
}
