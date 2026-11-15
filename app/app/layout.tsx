import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import TabNav from "./components/TabNav";

// T75: one font for the whole app, Lexend (made for easy reading). The font file sits in
// app/app/fonts/, so the build needs no network.
const lexend = localFont({
  src: "./fonts/Lexend-Variable.woff2",
  variable: "--font-lexend",
  weight: "100 900",
  display: "swap",
});

// The page title shown in the browser tab.
export const metadata: Metadata = {
  title: "Handover",
  description: "One patient record merged from three hospitals, with the source of every fact.",
};

// The wrapper around every page (T75): a rounded app window with the green rail of tabs
// on the left (across the top on a phone) and the page beside it.
// The disclaimer and the GitHub link are in components/Page.tsx, which every tab uses,
// so every tab shows them (CLAUDE.md app rule).
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`h-full ${lexend.variable}`}>
      <body className="min-h-full flex flex-col lg:p-5">
        <div className="flex-1 flex flex-col lg:flex-row bg-rail lg:rounded-[2.5rem] overflow-hidden">
          <TabNav />
          <div className="flex-1 min-w-0 flex flex-col xl:flex-row bg-mint lg:rounded-l-[2.5rem] overflow-hidden">
            {children}
          </div>
        </div>
      </body>
    </html>
  );
}
