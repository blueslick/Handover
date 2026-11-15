// The frame every tab uses (T75): the main column on the mint background, and an
// optional white panel on the right (it drops below the main column on a small screen).
// The disclaimer and the GitHub link live here so every tab shows them (CLAUDE.md app
// rule). A new tab must use this component.
export default function Page({ children, aside, asideLabel }: { children: React.ReactNode; aside?: React.ReactNode; asideLabel?: string }) {
  return (
    <>
      <main className="flex-1 min-w-0 flex flex-col gap-5 p-4 sm:p-8">
        {children}
        <footer className="mt-auto pt-4 text-sm text-soft flex flex-wrap gap-x-6 gap-y-1">
          <p>This project is a prototype and is not medical advice.</p>
          <a
            href="https://github.com/blueslick/Veritas-AI-Hackathon-"
            className="underline underline-offset-2 hover:text-ink"
          >
            Handover on GitHub
          </a>
        </footer>
      </main>
      {aside && (
        <aside aria-label={asideLabel} className="shrink-0 bg-white p-4 sm:p-8 flex flex-col gap-6 xl:w-[24rem]">
          {aside}
        </aside>
      )}
    </>
  );
}

// A white rounded card, the basic block of every page.
export function Card({ children, className = "", ...rest }: React.ComponentProps<"section">) {
  return (
    <section {...rest} className={`bg-white rounded-3xl p-5 sm:p-6 ${className}`}>
      {children}
    </section>
  );
}
