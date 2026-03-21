import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";
import { AppProvider } from "@/lib/app-context";
import { AppShell } from "@/components/layout/app-shell";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "India AI Engine — NSE Stock Market AI Prediction",
  description:
    "Production-grade AI prediction engine for India's NSE/BSE markets. Multi-agent analysis, ML models, F&O strategy, FII/DII tracking.",
  keywords: ["NSE", "BSE", "Nifty50", "stock prediction", "AI trading", "India stock market"],
  authors: [{ name: "India AI Engine" }],
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#F8FAFC" },
    { media: "(prefers-color-scheme: dark)", color: "#0A0F1E" },
  ],
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={inter.variable}>
      <body className="antialiased">
        <Providers>
          <AppProvider>
            <AppShell>{children}</AppShell>
          </AppProvider>
        </Providers>
      </body>
    </html>
  );
}
