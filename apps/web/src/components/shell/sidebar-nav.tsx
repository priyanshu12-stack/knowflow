"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

import { PRIMARY_NAV, SECONDARY_NAV, type NavItem } from "./nav-items";

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

const itemBase =
  "flex h-9 items-center gap-2.5 rounded-lg px-2.5 text-[14px] font-medium transition-colors";

function NavLink({ item, onNavigate }: { item: NavItem; onNavigate?: () => void }) {
  const pathname = usePathname();
  const Icon = item.icon;

  if (item.availableIn) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            role="link"
            aria-disabled="true"
            tabIndex={0}
            className={cn(itemBase, "cursor-not-allowed text-muted-foreground/80")}
          >
            <Icon aria-hidden="true" className="size-[18px]" strokeWidth={1.75} />
            <span className="flex-1">{item.label}</span>
            <span className="font-mono text-[11px] text-muted-foreground">
              <span className="sr-only">, not built yet, ships in milestone </span>
              {item.availableIn}
            </span>
          </span>
        </TooltipTrigger>
        <TooltipContent side="right">
          Not built yet. Ships in milestone {item.availableIn}.
        </TooltipContent>
      </Tooltip>
    );
  }

  const active = isActive(pathname, item.href);
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        itemBase,
        active
          ? "bg-accent text-accent-foreground"
          : "text-foreground/80 hover:bg-secondary hover:text-foreground",
      )}
    >
      <Icon aria-hidden="true" className="size-[18px]" strokeWidth={1.75} />
      {item.label}
    </Link>
  );
}

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex flex-1 flex-col justify-between gap-6">
      <nav aria-label="Primary">
        <ul className="flex flex-col gap-0.5">
          {PRIMARY_NAV.map((item) => (
            <li key={item.href}>
              <NavLink item={item} onNavigate={onNavigate} />
            </li>
          ))}
        </ul>
      </nav>
      <nav aria-label="Secondary">
        <ul className="flex flex-col gap-0.5">
          {SECONDARY_NAV.map((item) => (
            <li key={item.href}>
              <NavLink item={item} onNavigate={onNavigate} />
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
