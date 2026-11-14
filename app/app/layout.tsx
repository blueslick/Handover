import type { Metadata } from "next";
import "./globals.css";

// The page title shown in the browser tab.
export const metadata: Metadata = {
  title: "Handover",
  description: "One patient record merged from three hospitals, with the source of every fact.",
};

// The wrapper around every page. The body is a full-height column so the
// disclaimer line can sit at the bottom of each page.
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
