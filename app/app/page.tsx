// Home page: only the title and the required disclaimer line for now.
export default function Home() {
  return (
    <>
      <main className="flex-1 p-8">
        <h1 className="text-3xl font-semibold">Handover</h1>
      </main>
      {/* Required on every tab (see CLAUDE.md). */}
      <footer className="p-8 text-sm text-zinc-700">
        This project is a prototype and is not medical advice.
      </footer>
    </>
  );
}
