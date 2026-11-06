"use client";

import { Check, Copy, RefreshCw } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge, type StatusTone } from "@/components/ui/status-badge";
import { CHECK_HINTS, CHECK_LABELS, type DependencyCheck } from "@/lib/api/health";

import { useSystemStatus } from "./system-status-provider";

function checkTone(check: DependencyCheck): { tone: StatusTone; label: string } {
  if (check.state === "ok") return { tone: "ok", label: "Ready" };
  if (check.state === "missing") return { tone: "warning", label: "Needs setup" };
  return { tone: "danger", label: "Unavailable" };
}

function CopyCommand({ command }: { command: string }) {
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
      setFailed(false);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setFailed(true);
    }
  };
  return (
    <div className="mt-2 flex max-w-full items-center gap-1 rounded-lg border bg-background pl-3">
      <code className="min-w-0 flex-1 overflow-x-auto py-1.5 font-mono text-[12.5px] whitespace-nowrap">
        {command}
      </code>
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={copy}
        aria-label={copied ? "Command copied" : `Copy command: ${command}`}
      >
        {copied ? (
          <Check aria-hidden="true" className="text-success" />
        ) : (
          <Copy aria-hidden="true" />
        )}
      </Button>
      <span role="status" className="sr-only">
        {copied ? "Copied to clipboard" : failed ? "Copy failed; select the text instead" : ""}
      </span>
    </div>
  );
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
  const requiredDown = failing.filter((c) => c.required);
  if (requiredDown.length > 0) {
    const names = requiredDown.map((c) => CHECK_LABELS[c.name] ?? c.name).join(", ");
    return `${names} ${requiredDown.length === 1 ? "is" : "are"} unavailable. KnowFlow cannot work until ${requiredDown.length === 1 ? "it is" : "they are"} running.`;
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
          {Array.from({ length: 5 }, (_, i) => (
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
