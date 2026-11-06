"use client";

import { CircleCheck, CircleX, Info, LoaderCircle, TriangleExclamationPoint } from "lucide-react";
import { Toaster as Sonner, type ToasterProps } from "sonner";

/**
 * DRD §8 toast: short, actionable, non-blocking. Light theme only (DRD §2); status colour on the
 * icon, text in ink (docs/design-system.md contrast rules).
 */
function Toaster(props: ToasterProps) {
  return (
    <Sonner
      theme="light"
      className="toaster group"
      icons={{
        success: <CircleCheck className="size-4 text-success" />,
        info: <Info className="size-4 text-info" />,
        warning: <TriangleExclamationPoint className="size-4 text-warning" />,
        error: <CircleX className="size-4 text-danger" />,
        loading: <LoaderCircle className="size-4 motion-safe:animate-spin" />,
      }}
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--border-radius": "var(--radius)",
        } as React.CSSProperties
      }
      toastOptions={{ classNames: { toast: "cn-toast" } }}
      {...props}
    />
  );
}

export { Toaster };
