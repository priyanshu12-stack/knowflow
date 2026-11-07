import { requestJson } from "./client";
import { arr, int, nullableInt, nullableStr, obj, str } from "./validate";

export interface ActivityEvent {
  id: string;
  createdAt: string;
  actor: string;
  action: string;
  resourceType: string;
  resourceId: string | null;
  requestId: string | null;
  metadata: Record<string, unknown>;
}

export interface IngestionJobRow {
  id: string;
  documentId: string;
  documentName: string;
  status: string;
  stage: string | null;
  attempts: number;
  errorCode: string | null;
  errorMessage: string | null;
  createdAt: string;
  durationMs: number | null;
}

export interface ActivitySummary {
  documents: number;
  documentsReady: number;
  documentsProcessing: number;
  documentsFailed: number;
  chunks: number;
  questions7d: number;
  abstained7d: number;
  answerLatencyP50Ms: number | null;
  sqlQuestions7d: number;
  latestEvaluation: {
    id: string;
    label: string;
    recallAtK: number | null;
    mrr: number | null;
    cases: number;
    createdAt: string;
  } | null;
}

export type EventCategory =
  | "all"
  | "document"
  | "ingestion"
  | "chat"
  | "conversation"
  | "feedback"
  | "settings"
  | "evaluation"
  | "sql"
  | "workspace";

export async function fetchEvents(category: EventCategory, limit = 50, signal?: AbortSignal) {
  const qs = new URLSearchParams({ category, limit: String(limit) });
  return (
    await requestJson(
      `/api/v1/activity/events?${qs}`,
      (raw) => {
        const o = obj(raw, "events");
        return {
          total: int(o, "total", "events"),
          items: arr(o, "items", "events", (e, p) => {
            const eo = obj(e, p);
            return {
              id: str(eo, "id", p),
              createdAt: str(eo, "created_at", p),
              actor: str(eo, "actor", p),
              action: str(eo, "action", p),
              resourceType: str(eo, "resource_type", p),
              resourceId: nullableStr(eo, "resource_id", p),
              requestId: nullableStr(eo, "request_id", p),
              metadata: obj(eo.metadata, `${p}.metadata`),
            } satisfies ActivityEvent;
          }),
        };
      },
      { signal },
    )
  ).data;
}

export async function fetchJobs(status: "all" | "failed" | "active", signal?: AbortSignal) {
  return (
    await requestJson(
      `/api/v1/activity/jobs?status=${status}`,
      (raw) =>
        Array.isArray(raw)
          ? raw.map((j, i) => {
              const p = `jobs[${i}]`;
              const o = obj(j, p);
              return {
                id: str(o, "id", p),
                documentId: str(o, "document_id", p),
                documentName: str(o, "document_name", p),
                status: str(o, "status", p),
                stage: nullableStr(o, "stage", p),
                attempts: int(o, "attempts", p),
                errorCode: nullableStr(o, "error_code", p),
                errorMessage: nullableStr(o, "error_message", p),
                createdAt: str(o, "created_at", p),
                durationMs: nullableInt(o, "duration_ms", p),
              } satisfies IngestionJobRow;
            })
          : [],
      { signal },
    )
  ).data;
}

export async function fetchSummary(signal?: AbortSignal) {
  return (
    await requestJson(
      "/api/v1/activity/summary",
      (raw) => {
        const o = obj(raw, "summary");
        const le = o.latest_evaluation ? obj(o.latest_evaluation, "latest") : null;
        const num = (v: unknown) => (typeof v === "number" ? v : null);
        return {
          documents: int(o, "documents", "summary"),
          documentsReady: int(o, "documents_ready", "summary"),
          documentsProcessing: int(o, "documents_processing", "summary"),
          documentsFailed: int(o, "documents_failed", "summary"),
          chunks: int(o, "chunks", "summary"),
          questions7d: int(o, "questions_7d", "summary"),
          abstained7d: int(o, "abstained_7d", "summary"),
          answerLatencyP50Ms: num(o.answer_latency_p50_ms),
          sqlQuestions7d: int(o, "sql_questions_7d", "summary"),
          latestEvaluation: le
            ? {
                id: str(le, "id", "latest"),
                label: str(le, "label", "latest"),
                recallAtK: num(le.recall_at_k),
                mrr: num(le.mrr),
                cases: int(le, "cases", "latest"),
                createdAt: str(le, "created_at", "latest"),
              }
            : null,
        } satisfies ActivitySummary;
      },
      { signal },
    )
  ).data;
}

/** Plain-language description of an audit action (DRD §11 plain language). */
export function describeEvent(e: ActivityEvent): string {
  const m = e.metadata;
  switch (e.action) {
    case "document.created":
      return `Uploaded a ${String(m.file_type ?? "")} document`;
    case "document.new_version":
      return "Uploaded a new version of a document";
    case "document.reindexed":
      return "Re-indexed a duplicate upload";
    case "document.skipped":
      return "Skipped a duplicate upload";
    case "document.deleted":
      return "Deleted a document";
    case "document.retry":
      return "Queued a document for processing again";
    case "ingestion.succeeded":
      return `Indexed a document (${String(m.chunks ?? "?")} chunks)`;
    case "ingestion.failed":
      return `Processing failed (${String(m.error_code ?? "error")})`;
    case "ingestion.retry_scheduled":
      return `Processing will retry (${String(m.error_code ?? "error")})`;
    case "chat.answered":
      return m.abstained === true
        ? "Answered: no supporting source found"
        : `Answered a question with ${String(m.citations ?? 0)} citation(s)`;
    case "feedback.recorded":
      return `Feedback: ${m.rating === "helpful" ? "helpful" : "not helpful"}`;
    case "conversation.renamed":
      return "Renamed a conversation";
    case "conversation.deleted":
      return "Deleted a conversation";
    case "settings.models_saved":
      return "Saved model settings";
    case "settings.reindex":
      return `Queued ${String(m.queued ?? 0)} document(s) for re-indexing`;
    case "evaluation.run_queued":
      return `Started an evaluation run (${String(m.strategy ?? "")})`;
    case "evaluation.sample_loaded":
      return "Loaded the sample dataset";
    case "evaluation.cases_imported":
      return `Imported ${String(m.imported ?? 0)} evaluation case(s)`;
    case "sql.executed":
      return `Ran a read-only SQL query (${String(m.rows ?? 0)} rows)`;
    case "sql.clarification_required":
      return "SQL question needed clarification";
    case "sql.rejected":
      return "Rejected unsafe generated SQL";
    case "sql.connection_added":
      return "Connected a read-only database";
    case "workspace.renamed":
      return "Renamed the workspace";
    default:
      return e.action.replaceAll(".", " ").replaceAll("_", " ");
  }
}
