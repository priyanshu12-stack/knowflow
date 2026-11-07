"use client";

import { FlaskConical, MessagesSquare, Upload } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  describeEvent,
  fetchEvents,
  fetchSummary,
  type ActivityEvent,
  type ActivitySummary,
} from "@/lib/api/activity";

function Metric({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-xl border bg-card px-4 py-3">
      <dt className="text-[12px] text-muted-foreground">{label}</dt>
      <dd className="mt-1 font-mono text-[22px] font-semibold tabular-nums">{value}</dd>
      {note && <dd className="text-[12px] text-muted-foreground">{note}</dd>}
    </div>
  );
}

/** DRD §7.1: real metrics only (no demo counts), recent activity and quick actions. */
export function OverviewDashboard() {
  const [summary, setSummary] = useState<ActivitySummary | null>(null);
  const [events, setEvents] = useState<ActivityEvent[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchSummary(ctrl.signal).then(setSummary, () => !ctrl.signal.aborted && setFailed(true));
    fetchEvents("all", 8, ctrl.signal).then(
      (r) => setEvents(r.items),
      () => !ctrl.signal.aborted && setEvents([]),
    );
    return () => ctrl.abort();
  }, []);

  if (failed) return null; // the readiness panel above already explains why the API is unavailable

  const s = summary;
  return (
    <div className="flex flex-col gap-6">
      <section aria-labelledby="metrics">
        <h2 id="metrics" className="sr-only">
          Key metrics
        </h2>
        {s ? (
          <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Metric
              label="Documents indexed"
              value={`${s.documentsReady}`}
              note={
                s.documentsProcessing || s.documentsFailed
                  ? `${s.documentsProcessing} processing · ${s.documentsFailed} failed`
                  : `of ${s.documents} in the library`
              }
            />
            <Metric label="Searchable chunks" value={`${s.chunks}`} note="recursive strategy" />
            <Metric
              label="Questions (7 days)"
              value={`${s.questions7d}`}
              note={
                s.answerLatencyP50Ms !== null
                  ? `median answer ${(s.answerLatencyP50Ms / 1000).toFixed(0)} s · ${s.abstained7d} without a source`
                  : "none asked yet"
              }
            />
            <Metric
              label="Latest evaluation"
              value={
                s.latestEvaluation?.recallAtK != null
                  ? `R ${s.latestEvaluation.recallAtK.toFixed(2)}`
                  : "—"
              }
              note={
                s.latestEvaluation
                  ? `${s.latestEvaluation.label} · ${s.latestEvaluation.cases} cases`
                  : "no completed run yet"
              }
            />
          </dl>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-[86px] w-full" />
            ))}
          </div>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <section aria-labelledby="recent" className="rounded-xl border bg-card px-5 py-4">
          <div className="flex items-center justify-between">
            <h2 id="recent" className="text-[16px] font-semibold">
              Recent activity
            </h2>
            <Link href="/activity" className="text-[13px] text-primary hover:underline">
              View all
            </Link>
          </div>
          {events === null && <Skeleton className="mt-3 h-24 w-full" />}
          {events?.length === 0 && (
            <p className="mt-3 text-[14px] text-muted-foreground">Nothing has happened yet.</p>
          )}
          {events && events.length > 0 && (
            <ul className="mt-2 divide-y">
              {events.map((e) => (
                <li key={e.id} className="flex justify-between gap-4 py-2 text-[14px]">
                  <span>{describeEvent(e)}</span>
                  <time
                    dateTime={e.createdAt}
                    className="shrink-0 text-[12px] text-muted-foreground tabular-nums"
                  >
                    {new Date(e.createdAt).toLocaleTimeString(undefined, { timeStyle: "short" })}
                  </time>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="quick" className="rounded-xl border bg-card px-5 py-4">
          <h2 id="quick" className="text-[16px] font-semibold">
            Quick actions
          </h2>
          <div className="mt-3 flex flex-col gap-2">
            <Button asChild variant="outline" className="justify-start">
              <Link href="/library">
                <Upload aria-hidden="true" />
                Upload documents
              </Link>
            </Button>
            <Button asChild variant="outline" className="justify-start">
              <Link href="/ask">
                <MessagesSquare aria-hidden="true" />
                Ask a question
              </Link>
            </Button>
            <Button asChild variant="outline" className="justify-start">
              <Link href="/evaluation">
                <FlaskConical aria-hidden="true" />
                Run an evaluation
              </Link>
            </Button>
          </div>
        </section>
      </div>
    </div>
  );
}
