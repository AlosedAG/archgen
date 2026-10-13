import type { Metadata } from "next";
import { Inter, Poppins } from "next/font/google";

import { Providers } from "@/components/Providers";

import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const poppins = Poppins({ subsets: ["latin"], weight: ["600", "700", "800"], variable: "--font-poppins", display: "swap" });

export const metadata: Metadata = {
  title: { default: "ArchitectureScope", template: "%s · ArchitectureScope" },
  description: "HubSpot discovery, architecture, audit, and documentation.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${poppins.variable}`}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
