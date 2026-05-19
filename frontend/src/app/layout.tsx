import type { Metadata } from "next";
import { Fraunces, IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";

import { Grain } from "@/components/atoms/grain";
import { AppProviders } from "@/app/providers";

import "@/styles/globals.css";

const fontDisplay = Fraunces({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-display",
  weight: ["400", "500", "600", "700"],
});

const fontBody = IBM_Plex_Sans({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-body",
  weight: ["300", "400", "500", "600", "700"],
});

const fontMono = IBM_Plex_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-mono",
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "Glimmora Lawyer — Counsel Workspace",
  description:
    "A private workspace for litigators: evidence, research, rehearsal, drafting, and a single case-intelligence report.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${fontDisplay.variable} ${fontBody.variable} ${fontMono.variable}`}
    >
      <body className="relative min-h-screen font-body antialiased">
        <Grain />
        <AppProviders>
          <div className="relative z-10">{children}</div>
        </AppProviders>
      </body>
    </html>
  );
}
