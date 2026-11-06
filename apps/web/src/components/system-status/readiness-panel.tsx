"use client";

import { RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { CopyCommand } from "@/components/ui/copy-command";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge, type StatusTone } from "@/components/ui/status-badge";
import { CHECK_HINTS, CHECK_LABELS, type DependencyCheck } from "@/lib/api/health";

import { useSystemStatus } from "./system-status-provider";

function checkTone(check: DependencyCheck): { tone: StatusTone; label: string } {
  if (check.state === "ok") return { tone: "ok", label: "Ready" };
  if (check.state === "missing") return { tone: "warning", label: "Needs setup" };
  return { tone: "danger", label: "Unavailable" };
}

function CheckRow({ check }: { check: DependencyCheck }) {
  const { tone, label } = checkTone(check);
  return (
    // minmax(0, …) tracks stop long commands from widening the page on mobile.
    <li className="grid grid-cols-1 gap-x-6 gap-y-1.5 px-5 py-4 sm:grid-cols-[200px_140px_minmax(0,1fr)]">
      <div>
        <p className="font-medium">{CHECK_LABELS[check.name] ?? check.name}</p>
        {CHECK_HINTS[check.name] && (
          <p className="text-[12px] text-muted-foreground">{CHECK_HINTS[check.name]}</p>
        )}
      </div>
      <StatusBadge tone={tone} className="self-start">
        {label}
      </StatusBadge>
      <div className="min-w-0 text-muted-foreground">
        <span className={check.state === "ok" ? "font-mono text-[12.5px]" : undefined}>
          {check.detail}
        </span>
        {check.remediation && <CopyCommand command={check.remediation} />}
      </div>
    </li>
  );
}

function summaryLine(checks: DependencyCheck[]): string {
  const failing = checks.filter((c) => c.state !== "ok");
  if (failing.length === 0) return "All local services and models are ready.";
  const label = (list: DependencyCheck[]) =>
    list.map((c) => CHECK_LABELS[c.name] ?? c.name).join(", ");
  const down = failing.filter((c) => c.required && c.state === "unavailable");
  if (down.length > 0) {
    return `${label(down)} ${down.length === 1 ? "is" : "are"} unavailable. KnowFlow cannot work until ${down.length === 1 ? "it is" : "they are"} running.`;
  }
  const setup = failing.filter((c) => c.required);
  if (setup.length > 0) {
    return `${label(setup)} ${setup.length === 1 ? "needs" : "need"} setup. Run the command below, then select Re-check.`;
  }
  return `Services are running. ${failing.length} model${failing.length === 1 ? " is" : "s are"} not installed yet, so indexing and answers are unavailable until ${failing.length === 1 ? "it is" : "they are"} pulled.`;
}

export function ReadinessPanel() {
  const { status, checking, recheck } = useSystemStatus();

  return (
    <section
      id="system-readiness"
      aria-labelledby="readiness-heading"
      className="scroll-mt-20 rounded-xl border bg-card"
    >
      <div className="flex flex-wrap items-start justify-between gap-3 border-b px-5 py-4">
        <div>
          <h2 id="readiness-heading" className="text-[18px] font-semibold">
            System readiness
          </h2>
          <p className="mt-0.5 text-muted-foreground" aria-live="polite">
            {status.kind === "loading" && "Checking PostgreSQL, Ollama and local models…"}
            {status.kind === "loaded" && summaryLine(status.data.checks)}
            {status.kind === "error" && status.error.message}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {status.kind !== "loading" && (
            <span className="text-[12px] text-muted-foreground tabular-nums">
              Checked {status.checkedAt.toLocaleTimeString()}
            </span>
          )}
          <Button variant="outline" size="sm" onClick={recheck} disabled={checking}>
            <RefreshCw
              aria-hidden="true"
              className={checking ? "motion-safe:animate-spin" : undefined}
            />
            {checking ? "Checking…" : "Re-check"}
          </Button>
        </div>
      </div>

      {status.kind === "loading" && (
        <ul aria-label="Loading dependency checks" className="divide-y">
          {Array.from({ length: 6 }, (_, i) => (
            <li
              key={i}
              className="grid grid-cols-1 gap-x-6 gap-y-2 px-5 py-4 sm:grid-cols-[200px_140px_minmax(0,1fr)]"
            >
              <Skeleton className="h-4 w-36" />
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 w-full max-w-64" />
            </li>
          ))}
        </ul>
      )}

      {status.kind === "error" && (
        <div className="px-5 py-5">
          <StatusBadge tone="danger">API unreachable</StatusBadge>
          <p className="mt-2 max-w-prose text-muted-foreground">
            The web app could not reach the KnowFlow API, so the status of the database and local
            models is unknown. Start the API, then select Re-check.
          </p>
          <CopyCommand command="./scripts/dev.ps1 api" />
          {status.error.requestId && (
            <p className="mt-3 font-mono text-[12px] text-muted-foreground">
              Request ID: {status.error.requestId}
            </p>
          )}
        </div>
      )}

      {status.kind === "loaded" && (
        <ul className="divide-y">
          {status.data.checks.map((check) => (
            <CheckRow key={check.name} check={check} />
          ))}
        </ul>
      )}
    </section>
  );
}
