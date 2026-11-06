import { getJson } from "./client";

export type CheckState = "ok" | "unavailable" | "missing";
export type ReadyStatus = "ready" | "degraded" | "not_ready";

export interface DependencyCheck {
  name: string;
  state: CheckState;
  required: boolean;
  detail: string;
  remediation: string | null;
  latency_ms: number | null;
}

export interface ReadyResponse {
  status: ReadyStatus;
  checks: DependencyCheck[];
}

const STATES: readonly CheckState[] = ["ok", "unavailable", "missing"];
const STATUSES: readonly ReadyStatus[] = ["ready", "degraded", "not_ready"];

function fail(what: string): never {
  throw new TypeError(`invalid readiness payload: ${what}`);
}

/** Validates the payload instead of trusting a cast (API output is untrusted input). */
export function parseReadyResponse(raw: unknown): ReadyResponse {
  if (typeof raw !== "object" || raw === null) fail("not an object");
  const { status, checks } = raw as Record<string, unknown>;
  if (!STATUSES.includes(status as ReadyStatus)) fail("status");
  if (!Array.isArray(checks)) fail("checks");
  return {
    status: status as ReadyStatus,
    checks: checks.map((c, i): DependencyCheck => {
      if (typeof c !== "object" || c === null) fail(`checks[${i}]`);
      const r = c as Record<string, unknown>;
      if (typeof r.name !== "string" || typeof r.detail !== "string") fail(`checks[${i}].name`);
      if (!STATES.includes(r.state as CheckState)) fail(`checks[${i}].state`);
      return {
        name: r.name,
        state: r.state as CheckState,
        required: r.required === true,
        detail: r.detail,
        remediation: typeof r.remediation === "string" ? r.remediation : null,
        latency_ms: typeof r.latency_ms === "number" ? r.latency_ms : null,
      };
    }),
  };
}

export function fetchReadiness(signal?: AbortSignal) {
  // 503 is a documented readiness response carrying the same body.
  return getJson("/api/v1/health/ready", parseReadyResponse, {
    acceptStatuses: [503],
    timeoutMs: 15_000,
    signal,
  });
}

/** Human labels for check names (DRD §11: plain language). */
export const CHECK_LABELS: Record<string, string> = {
  postgres: "PostgreSQL",
  pgvector: "pgvector extension",
  database_schema: "Database schema",
  ollama: "Ollama runtime",
  generation_model: "Generation model",
  embedding_model: "Embedding model",
  ingestion_worker: "Ingestion worker",
};

/** What each optional model unlocks, shown under its label. */
export const CHECK_HINTS: Record<string, string> = {
  generation_model: "Needed to generate answers",
  embedding_model: "Needed to index and search documents",
  ingestion_worker: "Processes uploaded documents in the background",
};
