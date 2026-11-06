import { cn } from "@/lib/utils";

/** DRD §2/§14 mark: a folded page with linked evidence nodes. Stroke-only, no gradients. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={cn("size-6", className)}
    >
      <path d="M6 2.75h8.25l5 5V20A1.25 1.25 0 0 1 18 21.25H6A1.25 1.25 0 0 1 4.75 20V4A1.25 1.25 0 0 1 6 2.75Z" />
      <path d="M14.25 2.75v5h5" />
      <path d="M9 12.25 15 14M9 12.25l1.75 5" />
      <circle cx="9" cy="12.25" r="1.25" fill="currentColor" stroke="none" />
      <circle cx="15" cy="14" r="1.25" fill="currentColor" stroke="none" />
      <circle cx="10.75" cy="17.25" r="1.25" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-primary", className)}>
      <LogoMark />
      <span className="text-[17px] font-semibold tracking-tight text-foreground">KnowFlow</span>
    </span>
  );
}
