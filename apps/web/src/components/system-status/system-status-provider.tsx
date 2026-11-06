"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/api/client";
import { fetchReadiness, type ReadyResponse } from "@/lib/api/health";

export type SystemStatus =
  | { kind: "loading" }
  | { kind: "loaded"; data: ReadyResponse; checkedAt: Date; requestId: string | null }
  | { kind: "error"; error: ApiError; checkedAt: Date };

interface SystemStatusContextValue {
  status: SystemStatus;
  checking: boolean;
  recheck: () => void;
}

const SystemStatusContext = createContext<SystemStatusContextValue | null>(null);

const POLL_MS = 30_000;

export function SystemStatusProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<SystemStatus>({ kind: "loading" });
  // Starts true: the mount effect immediately begins the first check.
  const [checking, setChecking] = useState(true);
  const inflight = useRef<AbortController | null>(null);

  /** Async part only: every setState happens in a promise callback, never synchronously. */
  const load = useCallback(() => {
    inflight.current?.abort();
    const controller = new AbortController();
    inflight.current = controller;
    fetchReadiness(controller.signal)
      .then((res) =>
        setStatus({
          kind: "loaded",
          data: res.data,
          checkedAt: new Date(),
          requestId: res.requestId,
        }),
      )
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        const error =
          err instanceof ApiError
            ? err
            : new ApiError("unknown_error", "Could not check system status.", null, null);
        setStatus({ kind: "error", error, checkedAt: new Date() });
      })
      .finally(() => {
        if (inflight.current === controller) {
          inflight.current = null;
          setChecking(false);
        }
      });
  }, []);

  /** For event handlers and timers: show the checking state, then load. */
  const recheck = useCallback(() => {
    setChecking(true);
    load();
  }, [load]);

  useEffect(() => {
    load();
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") recheck();
    }, POLL_MS);
    return () => {
      window.clearInterval(id);
      inflight.current?.abort();
    };
  }, [load, recheck]);

  return (
    <SystemStatusContext.Provider value={{ status, checking, recheck }}>
      {children}
    </SystemStatusContext.Provider>
  );
}

export function useSystemStatus(): SystemStatusContextValue {
  const ctx = useContext(SystemStatusContext);
  if (!ctx) throw new Error("useSystemStatus must be used inside <SystemStatusProvider>");
  return ctx;
}

/** Summary used by the top bar: one of the DRD §6.2 states. */
export function summarize(status: SystemStatus): {
  tone: "ok" | "warning" | "danger" | "pending";
  label: string;
} {
  if (status.kind === "loading") return { tone: "pending", label: "Checking system…" };
  if (status.kind === "error") return { tone: "danger", label: "API unreachable" };
  switch (status.data.status) {
    case "ready":
      return { tone: "ok", label: "Local models ready" };
    case "degraded":
      return { tone: "warning", label: "Needs setup" };
    case "not_ready":
      return { tone: "danger", label: "Services unavailable" };
  }
}
