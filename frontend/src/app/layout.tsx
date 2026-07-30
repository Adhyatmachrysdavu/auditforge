import type { Metadata } from "next";
import { Space_Grotesk, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { LocaleProvider } from "@/i18n/LocaleProvider";
import { AuthProvider } from "@/lib/auth";

// Font non-default (bukan look Claude): Space Grotesk (UI) + JetBrains Mono (angka/CVSS)
const sans = Space_Grotesk({ subsets: ["latin"], variable: "--font-sans", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap" });

export const metadata: Metadata = {
  title: "AuditForge",
  description:
    "Sistem Triase Temuan Keamanan dan Penyusunan Laporan Audit Berbasis Kecerdasan Buatan",
};

// Dark mode no-flash: terapkan tema ke <html> SEBELUM render (satu selektor: data-theme)
const themeScript = `(function(){try{var t=localStorage.getItem('af-theme');if(!t){t=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}document.documentElement.setAttribute('data-theme',t);}catch(e){document.documentElement.setAttribute('data-theme','light');}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className={`${sans.variable} ${mono.variable}`}>
        <LocaleProvider>
          <AuthProvider>{children}</AuthProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
