import type { Metadata } from "next";
import "./globals.css";
import TabNav from "./components/TabNav";

// The page title shown in the browser tab.
export const metadata: Metadata = {
  title: "Handover",
  description: "One patient record merged from three hospitals, with the source of every fact.",
};

// The wrapper around every page: tabs at the top, the page in the middle, and the
// disclaimer at the bottom. Keeping the disclaimer here means every tab shows it
// (CLAUDE.md app rule), including tabs added later.
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full flex flex-col">
        <TabNav />
        {children}
        <footer className="p-4 sm:p-8 max-w-5xl w-full mx-auto text-sm text-zinc-700">
          This project is a prototype and is not medical advice.
        </footer>
      </body>
    </html>
  );
}
