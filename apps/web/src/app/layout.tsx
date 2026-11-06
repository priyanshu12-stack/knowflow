import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import type { Metadata } from "next";

import { AppShell } from "@/components/shell/app-shell";
import { SystemStatusProvider } from "@/components/system-status/system-status-provider";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "KnowFlow", template: "%s · KnowFlow" },
  description: "Answers grounded in your knowledge. Local-first document intelligence.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // Geist is self-hosted via next/font/local: no network needed at build time.
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body>
        <TooltipProvider delayDuration={300}>
          <SystemStatusProvider>
            <AppShell>{children}</AppShell>
          </SystemStatusProvider>
          <Toaster position="bottom-right" />
        </TooltipProvider>
      </body>
    </html>
  );
}
