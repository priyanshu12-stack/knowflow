"use client";

import { Menu } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { Wordmark } from "@/components/brand/logo";
import { summarize, useSystemStatus } from "@/components/system-status/system-status-provider";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { StatusBadge } from "@/components/ui/status-badge";

import { pageTitle } from "./nav-items";
import { SidebarNav } from "./sidebar-nav";

function SidebarContents({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col gap-6 px-3 py-5">
      <div className="flex flex-col gap-1 px-2.5">
        <Link href="/" onClick={onNavigate} className="w-fit rounded-md" aria-label="KnowFlow home">
          <Wordmark />
        </Link>
        {/* Single local workspace in v1 (TRD §2); becomes the persisted name in M1. */}
        <p className="pl-8 text-[12px] text-muted-foreground">Local workspace</p>
      </div>
      <SidebarNav onNavigate={onNavigate} />
    </div>
  );
}

function SystemIndicator() {
  const { status } = useSystemStatus();
  const { tone, label } = summarize(status);
  return (
    <Link
      href="/#system-readiness"
      className="rounded-lg px-2 py-1 text-foreground hover:bg-secondary"
      aria-label={`System status: ${label}. View details.`}
    >
      <StatusBadge tone={tone}>{label}</StatusBadge>
    </Link>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <div className="min-h-dvh">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2 focus:shadow"
      >
        Skip to content
      </a>

      {/* DRD §4/§6.1: fixed 240px sidebar on desktop; drawer below 1024px (DRD §10). */}
      <aside className="fixed inset-y-0 left-0 hidden w-60 border-r bg-surface lg:block">
        <SidebarContents />
      </aside>

      <div className="flex min-h-dvh flex-col lg:pl-60">
        {/* DRD §6.2: quiet 56px top bar */}
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/95 px-4 md:px-6 lg:px-8">
          <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
            <SheetTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="lg:hidden"
                aria-label="Open navigation"
              >
                <Menu aria-hidden="true" className="size-5" strokeWidth={1.75} />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-64 bg-surface p-0">
              <SheetTitle className="sr-only">Navigation</SheetTitle>
              <SidebarContents onNavigate={() => setDrawerOpen(false)} />
            </SheetContent>
          </Sheet>
          <p className="flex-1 truncate text-[14px] font-medium text-foreground">
            {pageTitle(pathname)}
          </p>
          <SystemIndicator />
        </header>

        <main
          id="main"
          tabIndex={-1}
          className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-6 outline-none md:px-6 lg:px-8 lg:py-8"
        >
          {children}
        </main>
      </div>
    </div>
  );
}
