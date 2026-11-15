import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import TabNav from "./components/TabNav";
import { liveRuns, SAMPLE_IDS } from "@/lib/records";

// T81: IBM Plex Sans for everything, IBM Plex Mono only for raw record text. The font
// files sit in app/app/fonts/, so the build needs no network.
const plexSans = localFont({
  src: [
    { path: "./fonts/ibm-plex-sans-latin-400-normal.woff2", weight: "400", style: "normal" },
    { path: "./fonts/ibm-plex-sans-latin-500-normal.woff2", weight: "500", style: "normal" },
    { path: "./fonts/ibm-plex-sans-latin-600-normal.woff2", weight: "600", style: "normal" },
  ],
  variable: "--font-plex-sans",
  display: "swap",
});
const plexMono = localFont({
  src: "./fonts/ibm-plex-mono-latin-400-normal.woff2",
  weight: "400",
  variable: "--font-plex-mono",
  display: "swap",
});

// The page title shown in the browser tab.
export const metadata: Metadata = {
  title: "Handover",
  description: "One patient record merged from three hospitals, with the source of every fact.",
};

// The wrapper around every page (T81): the bar of tabs across the top, then the page.
// The disclaimer and the GitHub link are in components/Page.tsx, which every tab uses,
// so every tab shows them (CLAUDE.md app rule).
export default function RootLayout({ children }: { children: React.ReactNode }) {
  // The sample patients for the bar's list. On Daniel's laptop, live runs (T58) are listed
  // too; on the public link there are none.
  const demo = SAMPLE_IDS.filter((id) => id.startsWith("D"));
  const working = SAMPLE_IDS.filter((id) => !id.startsWith("D"));
  const live = liveRuns().map((p) => p.patient_id);
  return (
    <html lang="en" className={`${plexSans.variable} ${plexMono.variable}`}>
      <body>
        <div className="flex min-h-screen flex-col">
          <TabNav demo={demo} working={working} live={live} />
          {children}
        </div>
      </body>
    </html>
  );
}
