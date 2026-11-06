import {
  Activity,
  BookOpen,
  Cpu,
  Database,
  Files,
  FlaskConical,
  LayoutDashboard,
  MessagesSquare,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  /**
   * Milestone that ships this page. Pages not yet built render disabled with this
   * explanation (DRD §13 "Disabled" state; ADR-000 G-7) instead of linking to a dead end.
   */
  availableIn?: string;
}

// DRD §5 icon mapping, DRD §6.1 order.
export const PRIMARY_NAV: NavItem[] = [
  { label: "Overview", href: "/", icon: LayoutDashboard },
  { label: "Knowledge Library", href: "/library", icon: Files },
  { label: "Ask KnowFlow", href: "/ask", icon: MessagesSquare, availableIn: "M4" },
  { label: "SQL Analyst", href: "/sql", icon: Database, availableIn: "M6" },
  { label: "Evaluation Lab", href: "/evaluation", icon: FlaskConical, availableIn: "M5" },
];

export const SECONDARY_NAV: NavItem[] = [
  { label: "Models & Settings", href: "/settings", icon: Cpu, availableIn: "M3" },
  { label: "Activity", href: "/activity", icon: Activity, availableIn: "M7" },
  { label: "Help", href: "/help", icon: BookOpen, availableIn: "M8" },
];

const ALL = [...PRIMARY_NAV, ...SECONDARY_NAV];

export function pageTitle(pathname: string): string {
  const match = ALL.find((item) =>
    item.href === "/" ? pathname === "/" : pathname.startsWith(item.href),
  );
  return match?.label ?? "KnowFlow";
}
