// The frame every tab uses (T81): the patient banner and a thin bar of controls across the
// top (both optional), then the main column and an optional panel on the right (it drops
// below the main column on a small screen).
// The disclaimer and the GitHub link live here so every tab shows them (CLAUDE.md app
// rule). A new tab must use this component.
export default function Page({
  children,
  aside,
  asideLabel,
  banner,
  bar,
}: {
  children: React.ReactNode;
  aside?: React.ReactNode;
  asideLabel?: string;
  banner?: React.ReactNode;
  bar?: React.ReactNode;
}) {
  return (
    <div className="flex min-w-0 flex-1 flex-col">
      {banner}
      {bar}
      <div className="flex min-w-0 flex-1 flex-col xl:flex-row">
        <main className="flex min-w-0 flex-1 flex-col gap-4 p-4 sm:px-6">
          {children}
          <footer className="mt-auto flex flex-wrap gap-x-6 gap-y-1 pt-2 text-xs text-quiet">
            <p>This project is a prototype and is not medical advice.</p>
            {/* Opens in a new tab, so the reader keeps their place in the app (Abby's review). */}
            <a href="https://github.com/blueslick/Handover" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-ink">
              Handover on GitHub<span className="sr-only"> (opens in a new tab)</span>
            </a>
          </footer>
        </main>
        {aside && (
          <aside aria-label={asideLabel} className="flex shrink-0 flex-col gap-3 border-t border-line bg-surface p-4 sm:px-6 xl:w-[27rem] xl:border-l xl:border-t-0">
            {aside}
          </aside>
        )}
      </div>
    </div>
  );
}

// A white bordered box, the basic block of every page. One level only: no box inside a box.
export function Card({ children, className = "", ...rest }: React.ComponentProps<"section">) {
  return (
    <section {...rest} className={`rounded-box border border-line bg-surface p-3 ${className}`}>
      {children}
    </section>
  );
}

// A box with a title strip and a table or list inside (T81).
export function Box({ title, right, children, id, tone }: { title: React.ReactNode; right?: React.ReactNode; children: React.ReactNode; id?: string; tone?: "warn" }) {
  return (
    <section aria-labelledby={id} className={`min-w-0 scroll-mt-28 rounded-box border bg-surface ${tone === "warn" ? "border-warn-line" : "border-line"}`}>
      <div className={`flex min-h-9 flex-wrap items-center gap-2 rounded-t-[5px] border-b px-3 py-1 ${tone === "warn" ? "border-warn-line bg-warn-bg" : "border-line"}`}>
        <h2 id={id} className="text-base font-semibold">
          {title}
        </h2>
        {right && <span className="ml-auto text-xs text-quiet">{right}</span>}
      </div>
      {children}
    </section>
  );
}
