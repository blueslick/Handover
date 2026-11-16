"use client";
// The bar across the top of every page (T81): the app's name, the three tabs, and the
// patient box. The current tab is marked in words (for screen readers) and with a navy
// underline and bold text, not by colour alone. Add a tab here when its page exists.
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useLayoutEffect, useRef } from "react";

const TABS = [
  // T68 item 24: nothing can be uploaded here, so the tab says it is a replay.
  { href: "/upload", label: "Records replay" },
  { href: "/", label: "Doctor screen" },
  { href: "/how-we-tested", label: "How we tested" },
];

// The patient box. A plain GET form: submitting it puts the ID in the address, so it
// works without JavaScript. It keeps showing the ID that is in the address.
function PatientBox({ demo, working, live, suffix = "" }: { demo: string[]; working: string[]; live: string[]; suffix?: string }) {
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
    <div className="flex flex-wrap items-center gap-2">
      <form action="/" method="get" className="flex items-center gap-2">
        <label htmlFor={`id${suffix}`} className="text-quiet">
          Patient ID
        </label>
        <input id={`id${suffix}`} name="id" type="text" key={current} defaultValue={current} placeholder="e.g. D001" autoComplete="off" className="h-8 w-24 rounded-ctl border border-line-strong bg-surface px-2" />
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
  const headerRef = useRef<HTMLElement>(null);
  const navRef = useRef<HTMLElement>(null);
  const barRef = useRef<HTMLSpanElement>(null);

  // T94: one navy underline that slides to the current tab instead of jumping. It is moved
  // by hand (no React state), so nothing re-renders. Before this runs (or with JavaScript
  // off) each tab draws its own underline, so the current tab is always marked. The first
  // placement has no animation, so the bar doesn't slide in from the left on page load,
  // and people who ask their system for less motion get no slide at all.
  useLayoutEffect(() => {
    const nav = navRef.current;
    const bar = barRef.current;
    if (!nav || !bar) return;
    const place = () => {
      const current = nav.querySelector<HTMLElement>('a[aria-current="page"]');
      if (!current) {
        bar.style.opacity = "0";
        return;
      }
      bar.style.width = `${current.offsetWidth}px`;
      bar.style.transform = `translateX(${current.offsetLeft}px)`;
      bar.style.opacity = "1";
    };
    place();
    nav.dataset.bar = "on";
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const frame = requestAnimationFrame(() => {
      if (!calm) bar.style.transition = "transform 250ms ease-out, width 250ms ease-out";
    });
    // Tabs change width when the window is resized or the fonts load: place it again.
    const watch = new ResizeObserver(place);
    watch.observe(nav);
    return () => {
      cancelAnimationFrame(frame);
      watch.disconnect();
    };
  }, [pathname]);

  // T94: the bar stays pinned to the top of the window. Its height is shared as --nav-h so
  // the patient banner (pinned on wide screens) sits right under it, and "Go to row" jumps
  // land below both.
  useLayoutEffect(() => {
    const header = headerRef.current;
    if (!header) return;
    const share = () => document.documentElement.style.setProperty("--nav-h", `${header.offsetHeight}px`);
    share();
    const watch = new ResizeObserver(share);
    watch.observe(header);
    return () => watch.disconnect();
  }, []);

  return (
    <>
      <header ref={headerRef} className="sticky top-0 z-40 flex flex-wrap items-center gap-x-6 gap-y-1 border-b border-line bg-surface px-4 py-1 sm:px-6 sm:py-0">
        {/* T94: the app's name with its icon (same drawing as app/app/icon.svg: three hospital
            records stacked, the merged one in front with a medical cross). Drawn inline so it
            needs no extra file; aria-hidden because the word "Handover" already names the app. */}
        <span className="flex items-center gap-2 text-base font-semibold">
          <svg aria-hidden="true" viewBox="0 0 64 64" width="28" height="28" className="shrink-0">
            <defs>
              <linearGradient id="handover-logo-bg" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stopColor="#1E3A8A" />
                <stop offset="1" stopColor="#172554" />
              </linearGradient>
            </defs>
            <rect width="64" height="64" rx="14" fill="url(#handover-logo-bg)" />
            <rect x="23" y="9" width="29" height="35" rx="5" fill="#FFFFFF" fillOpacity="0.28" />
            <rect x="17.5" y="14" width="29" height="35" rx="5" fill="#FFFFFF" fillOpacity="0.55" />
            <rect x="12" y="19" width="29" height="36" rx="5" fill="#FFFFFF" />
            <path d="M26.5 29.5v15M19 37h15" stroke="#1E3A8A" strokeWidth="5" strokeLinecap="round" />
          </svg>
          Handover
        </span>
        <nav ref={navRef} aria-label="Tabs" className="group relative flex self-stretch">
          {TABS.map((tab) => {
            const current = tab.href === "/" ? pathname === "/" : pathname.startsWith(tab.href);
            return (
              <Link
                key={tab.href}
                href={tab.href}
                aria-current={current ? "page" : undefined}
                className={`flex min-h-11 items-center border-b-2 px-3 ${current ? "border-accent font-semibold text-ink group-data-[bar=on]:border-transparent" : "border-transparent text-quiet hover:text-ink"}`}
              >
                {tab.label}
                {current && <span className="sr-only"> (current tab)</span>}
              </Link>
            );
          })}
          {/* The sliding underline (see above). Hidden from screen readers: the current tab is
              already named in words. */}
          <span ref={barRef} aria-hidden="true" className="pointer-events-none absolute bottom-0 left-0 h-[2px] bg-accent opacity-0" />
        </nav>
        {/* The patient box reads the address, so it waits for the page to be ready. On wider
            screens it sits in the pinned bar; on phones it gets its own row under the bar (below),
            so the pinned part stays short and doesn't cover the page. */}
        <div className="hidden sm:ml-auto sm:block">
          <Suspense fallback={null}>
            <PatientBox demo={demo} working={working} live={live} />
          </Suspense>
        </div>
      </header>
      <div className="border-b border-line bg-surface px-4 py-1 sm:hidden">
        <Suspense fallback={null}>
          <PatientBox demo={demo} working={working} live={live} suffix="-phone" />
        </Suspense>
      </div>
    </>
  );
}
