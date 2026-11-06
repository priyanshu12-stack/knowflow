import { CircleCheck, CircleX, LoaderCircle, TriangleExclamationPoint } from "lucide-react";

import { cn } from "@/lib/utils";

export type StatusTone = "ok" | "warning" | "danger" | "pending";

const ICONS = {
  ok: { Icon: CircleCheck, className: "text-success" },
  warning: { Icon: TriangleExclamationPoint, className: "text-warning" },
  danger: { Icon: CircleX, className: "text-danger" },
  pending: { Icon: LoaderCircle, className: "text-muted-foreground motion-safe:animate-spin" },
} as const;

/**
 * DRD §8 status badge: icon + text, never colour alone (DRD §11). The label stays in ink
 * because some status colours are below 4.5:1 for text (see docs/design-system.md).
 */
export function StatusBadge({
  tone,
  children,
  className,
}: {
  tone: StatusTone;
  children: React.ReactNode;
  className?: string;
}) {
  const { Icon, className: iconClass } = ICONS[tone];
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-[13px] font-medium", className)}>
      <Icon aria-hidden="true" className={cn("size-4 shrink-0", iconClass)} strokeWidth={2} />
      <span>{children}</span>
    </span>
  );
}
