"use client";

import { RotateCw } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge, type StatusTone } from "@/components/ui/status-badge";
import {
  describeEvent,
  fetchEvents,
  fetchJobs,
  type ActivityEvent,
  type EventCategory,
  type IngestionJobRow,
} from "@/lib/api/activity";
import { ApiError } from "@/lib/api/client";

const CATEGORIES: { id: EventCategory; label: string }[] = [
  { id: "all", label: "All" },
  { id: "document", label: "Documents" },
  { id: "ingestion", label: "Ingestion" },
  { id: "chat", label: "Questions" },
  { id: "sql", label: "SQL" },
  { id: "evaluation", label: "Evaluation" },
  { id: "settings", label: "Settings" },
];

const JOB_TONE: Record<string, StatusTone> = {
  succeeded: "ok",
  failed: "danger",
  running: "pending",
  queued: "neutral",
};

function when(iso: string) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "medium" });
}

/** PRD §4 Activity / Logs: ingestion jobs, failures, request ids, safe events and latency. */
export function ActivityView() {
  const [tab, setTab] = useState<"events" | "jobs">("events");
  const [category, setCategory] = useState<EventCategory>("all");
  const [jobFilter, setJobFilter] = useState<"all" | "failed" | "active">("all");
  const [events, setEvents] = useState<ActivityEvent[] | null>(null);
  const [jobs, setJobs] = useState<IngestionJobRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const ctrl = new AbortController();
    const fail = (err: unknown) =>
      !ctrl.signal.aborted &&
      setError(err instanceof ApiError ? err.message : "Activity couldn't be loaded.");
    if (tab === "events") {
      fetchEvents(category, 100, ctrl.signal).then((r) => {
        setEvents(r.items);
        setError(null);
      }, fail);
    } else {
      fetchJobs(jobFilter, ctrl.signal).then((r) => {
        setJobs(r);
        setError(null);
      }, fail);
    }
    return () => ctrl.abort();
  }, [tab, category, jobFilter, tick]);

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[26px] leading-tight font-semibold tracking-tight">Activity</h1>
          <p className="mt-1 max-w-prose text-[15px] text-muted-foreground">
            What happened in this workspace, with the request ID to find it in the API log. Only
            ids, counts and statuses are recorded, never document text, questions or passwords.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => setTick((t) => t + 1)}>
          <RotateCw aria-hidden="true" />
          Refresh
        </Button>
      </header>

      <div role="tablist" aria-label="Activity views" className="flex gap-1 border-b">
        {(
          [
            ["events", "Events"],
            ["jobs", "Ingestion jobs"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            role="tab"
            type="button"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className="-mb-px border-b-2 border-transparent px-3 py-2 text-[14px] font-medium text-muted-foreground aria-selected:border-primary aria-selected:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            {label}
          </button>
        ))}
      </div>

      {error && (
        <div role="alert" className="rounded-xl border bg-card p-5">
          <StatusBadge tone="danger">Activity unavailable</StatusBadge>
          <p className="mt-2 text-muted-foreground">{error}</p>
        </div>
      )}

      {tab === "events" && (
        <section aria-label="Events" className="rounded-xl border bg-card">
          <div
            className="flex flex-wrap gap-1 border-b px-4 py-3"
            role="group"
            aria-label="Filter events"
          >
            {CATEGORIES.map((c) => (
              <Button
                key={c.id}
                size="sm"
                variant={category === c.id ? "secondary" : "ghost"}
                aria-pressed={category === c.id}
                onClick={() => setCategory(c.id)}
              >
                {c.label}
              </Button>
            ))}
          </div>
          {events === null && !error && <Skeleton className="m-4 h-32" />}
          {events?.length === 0 && (
            <p className="px-5 py-8 text-center text-muted-foreground">
              Nothing recorded yet. Upload a document or ask a question and it will appear here.
            </p>
          )}
          {events && events.length > 0 && (
            <div className="relative overflow-x-auto">
              <table className="w-full min-w-[720px] text-[14px]">
                <caption className="sr-only">Audit events</caption>
                <thead>
                  <tr className="border-b text-left text-[12px] text-muted-foreground">
                    <th className="px-5 py-2 font-medium">When</th>
                    <th className="py-2 font-medium">What happened</th>
                    <th className="py-2 font-medium">By</th>
                    <th className="px-5 py-2 font-medium">Request ID</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((e) => (
                    <tr key={e.id} className="border-b last:border-0">
                      <td className="px-5 py-2 whitespace-nowrap text-muted-foreground tabular-nums">
                        {when(e.createdAt)}
                      </td>
                      <td className="py-2">
                        {describeEvent(e)}
                        {typeof e.metadata.latency_ms === "number" && (
                          <span className="ml-2 font-mono text-[12px] text-muted-foreground">
                            {(e.metadata.latency_ms / 1000).toFixed(1)} s
                          </span>
                        )}
                      </td>
                      <td className="py-2 text-muted-foreground">
                        {e.actor === "worker" ? "Worker" : "You"}
                      </td>
                      <td className="px-5 py-2 font-mono text-[12px] text-muted-foreground">
                        {e.requestId ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {tab === "jobs" && (
        <section aria-label="Ingestion jobs" className="rounded-xl border bg-card">
          <div
            className="flex flex-wrap gap-1 border-b px-4 py-3"
            role="group"
            aria-label="Filter jobs"
          >
            {(["all", "failed", "active"] as const).map((f) => (
              <Button
                key={f}
                size="sm"
                variant={jobFilter === f ? "secondary" : "ghost"}
                aria-pressed={jobFilter === f}
                onClick={() => setJobFilter(f)}
              >
                {f === "all" ? "All" : f === "failed" ? "Failed" : "Queued or running"}
              </Button>
            ))}
          </div>
          {jobs === null && !error && <Skeleton className="m-4 h-32" />}
          {jobs?.length === 0 && (
            <p className="px-5 py-8 text-center text-muted-foreground">
              No ingestion jobs match this filter.
            </p>
          )}
          {jobs && jobs.length > 0 && (
            <div className="relative overflow-x-auto">
              <table className="w-full min-w-[720px] text-[14px]">
                <caption className="sr-only">Ingestion jobs</caption>
                <thead>
                  <tr className="border-b text-left text-[12px] text-muted-foreground">
                    <th className="px-5 py-2 font-medium">Document</th>
                    <th className="py-2 font-medium">Status</th>
                    <th className="py-2 text-right font-medium">Attempts</th>
                    <th className="py-2 text-right font-medium">Duration</th>
                    <th className="px-5 py-2 font-medium">Started</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((j) => (
                    <tr key={j.id} className="border-b last:border-0">
                      <td className="px-5 py-2">
                        <Link
                          className="font-medium hover:underline"
                          href={`/library?document=${j.documentId}`}
                        >
                          {j.documentName}
                        </Link>
                        {j.errorMessage && (
                          <p className="text-[13px] text-muted-foreground">
                            {j.errorMessage}{" "}
                            <span className="font-mono text-[12px]">({j.errorCode})</span>
                          </p>
                        )}
                      </td>
                      <td className="py-2">
                        <StatusBadge tone={JOB_TONE[j.status] ?? "neutral"}>
                          {j.status}
                          {j.stage ? ` · ${j.stage}` : ""}
                        </StatusBadge>
                      </td>
                      <td className="py-2 text-right tabular-nums">{j.attempts}</td>
                      <td className="py-2 text-right font-mono text-[13px] tabular-nums">
                        {j.durationMs === null ? "—" : `${(j.durationMs / 1000).toFixed(1)} s`}
                      </td>
                      <td className="px-5 py-2 whitespace-nowrap text-muted-foreground tabular-nums">
                        {when(j.createdAt)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
