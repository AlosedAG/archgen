import type { Metadata } from "next";
import { Bricolage_Grotesque, Public_Sans } from "next/font/google";

import { Providers } from "@/components/Providers";
import { THEME_SCRIPT } from "@/components/ThemeToggle";

import "./globals.css";

const display = Bricolage_Grotesque({ subsets: ["latin"], variable: "--font-display", display: "swap" });
const body = Public_Sans({ subsets: ["latin"], variable: "--font-public", display: "swap" });

export const metadata: Metadata = {
  title: { default: "The Hub Zone", template: "%s · The Hub Zone" },
  description: "HubSpot discovery, architecture, audit, and documentation.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // data-theme is set before paint by THEME_SCRIPT, so the server markup can't match it.
    <html lang="en" className={`${display.variable} ${body.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
