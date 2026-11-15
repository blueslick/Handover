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
    <html lang="en" className={lexend.variable}>
      <body className="lg:p-5">
        {/* T75 fix: the window is an ordinary block that is at least as tall as the screen and
            grows with the page, so the whole page scrolls. (Before, it was squeezed to the
            screen's height in Safari and the rest of the page was cut off.) */}
        <div className="flex min-h-screen flex-col bg-rail lg:min-h-[calc(100vh-2.5rem)] lg:flex-row lg:rounded-[2.5rem] lg:overflow-hidden">
          <TabNav />
          <div className="flex min-w-0 flex-auto flex-col bg-mint lg:flex-1 lg:rounded-l-[2.5rem] xl:flex-row">
            {children}
          </div>
        </div>
      </body>
    </html>
  );
}
