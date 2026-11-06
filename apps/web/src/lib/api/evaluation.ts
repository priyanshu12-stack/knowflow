import { ApiError, invalidResponse, requestJson, toApiError } from "./client";
import { arr, int, nullableStr, obj, str, type Obj } from "./validate";

export interface Dataset {
  id: string;
  name: string;
  version: string;
  description: string | null;
  cases: number;
  devCases: number;
  testCases: number;
  runs: number;
  missingDocuments: string[];
}

export type RunStatus = "queued" | "running" | "succeeded" | "failed";

export interface Aggregate {
  cases?: number;
  retrieval_cases?: number;
  recall_at_k?: number | null;
  precision_at_k?: number | null;
  mrr?: number | null;
  ndcg_at_k?: number | null;
  hit_at_k?: number | null;
  abstention_correct?: number | null;
  abstention_correct_n?: number;
  citation_precision?: number | null;
  citation_precision_n?: number;
  injection_resisted?: number | null;
  injection_resisted_n?: number;
  retrieval_ms_p50?: number | null;
  retrieval_ms_p95?: number | null;
  latency_ms_p50?: number | null;
  latency_ms_p95?: number | null;
  errors?: number;
  failure_categories?: Record<string, number>;
}

export interface Run {
  id: string;
  datasetId: string;
  label: string;
  strategy: string;
  modelId: string | null;
  status: RunStatus;
  progress: number;
  total: number;
  config: Record<string, unknown>;
  aggregate: Aggregate;
  error: string | null;
  createdAt: string;
  completedAt: string | null;
}

export interface RetrievedPassage {
  chunk_id: string;
  document_name: string;
  page_start: number | null;
  page_end: number | null;
  section_path: string | null;
  score: number;
  ranks: Record<string, number>;
  relevant: boolean;
  excerpt: string;
}

export interface CaseResult {
  caseId: string;
  externalId: string;
  split: string;
  question: string;
  referenceAnswer: string | null;
  answerable: boolean;
  expectedEvidence: { document: string; quote?: string; page?: number }[];
  tags: string[];
  retrieved: RetrievedPassage[];
  answer: string | null;
  metrics: Record<string, number | boolean>;
  failureCategory: string | null;
  latencyMs: number | null;
  error: string | null;
}

export interface RunDetail extends Run {
  results: CaseResult[];
}

export interface RunConfig {
  preset: "S1" | "S2" | "S3" | "S4" | "custom";
  chunk_strategy?: "fixed" | "recursive";
  mode?: "dense" | "lexical" | "hybrid";
  rerank?: boolean;
  top_k: number;
  split: "dev" | "test" | "all";
  generate_answers: boolean;
  label?: string;
}

const STATUSES = ["queued", "running", "succeeded", "failed"] as const;

function parseDataset(raw: unknown, p = "dataset"): Dataset {
  const o = obj(raw, p);
  return {
    id: str(o, "id", p),
    name: str(o, "name", p),
    version: str(o, "version", p),
    description: nullableStr(o, "description", p),
    cases: int(o, "cases", p),
    devCases: int(o, "dev_cases", p),
    testCases: int(o, "test_cases", p),
    runs: int(o, "runs", p),
    missingDocuments: arr(o, "missing_documents", p, (x) => String(x)),
  };
}

function parseRun(raw: unknown, p = "run"): Run {
  const o = obj(raw, p);
  const status = str(o, "status", p);
  return {
    id: str(o, "id", p),
    datasetId: str(o, "dataset_id", p),
    label: str(o, "label", p),
    strategy: str(o, "strategy", p),
    modelId: nullableStr(o, "model_id", p),
    status: (STATUSES as readonly string[]).includes(status) ? (status as RunStatus) : "failed",
    progress: int(o, "progress", p),
    total: int(o, "total", p),
    config: obj(o.config, `${p}.config`),
    aggregate: obj(o.aggregate_metrics, `${p}.aggregate`) as Aggregate,
    error: nullableStr(o, "error", p),
    createdAt: str(o, "created_at", p),
    completedAt: nullableStr(o, "completed_at", p),
  };
}

function parseResult(raw: unknown, p: string): CaseResult {
  const o: Obj = obj(raw, p);
  return {
    caseId: str(o, "case_id", p),
    externalId: str(o, "external_id", p),
    split: str(o, "split", p),
    question: str(o, "question", p),
    referenceAnswer: nullableStr(o, "reference_answer", p),
    answerable: o.answerable === true,
    expectedEvidence: Array.isArray(o.expected_evidence)
      ? (o.expected_evidence as CaseResult["expectedEvidence"])
      : [],
    tags: Array.isArray(o.tags) ? o.tags.map(String) : [],
    retrieved: Array.isArray(o.retrieved) ? (o.retrieved as RetrievedPassage[]) : [],
    answer: nullableStr(o, "answer", p),
    metrics: obj(o.metrics, `${p}.metrics`) as CaseResult["metrics"],
    failureCategory: nullableStr(o, "failure_category", p),
    latencyMs: typeof o.latency_ms === "number" ? o.latency_ms : null,
    error: nullableStr(o, "error", p),
  };
}

export async function fetchDatasets(signal?: AbortSignal) {
  return (
    await requestJson(
      "/api/v1/evaluations/datasets",
      (raw) => (Array.isArray(raw) ? raw.map((d, i) => parseDataset(d, `datasets[${i}]`)) : []),
      { signal },
    )
  ).data;
}

export async function createDataset(name: string, version: string) {
  return (
    await requestJson("/api/v1/evaluations/datasets", (r) => parseDataset(r), {
      method: "POST",
      json: { name, version },
    })
  ).data;
}

export async function loadSample() {
  return (
    await requestJson(
      "/api/v1/evaluations/sample",
      (raw) => {
        const o = obj(raw, "sample");
        return {
          datasetId: str(o, "dataset_id", "sample"),
          queued: int(o, "documents_queued", "sample"),
          existing: int(o, "documents_existing", "sample"),
        };
      },
      { method: "POST", timeoutMs: 60_000 },
    )
  ).data;
}

/** Multipart upload of CSV/JSONL cases; returns the import summary with row errors. */
export async function importCases(datasetId: string, file: File) {
  const form = new FormData();
  form.append("file", file, file.name);
  const res = await fetch(
    `/api/v1/evaluations/datasets/${encodeURIComponent(datasetId)}/cases/import`,
    { method: "POST", body: form, headers: { Accept: "application/json" } },
  );
  const requestId = res.headers.get("X-Request-ID");
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    throw invalidResponse(res.status, requestId);
  }
  if (!res.ok) throw toApiError(res.status, body, requestId);
  const o = obj(body, "import");
  return {
    imported: int(o, "imported", "import"),
    errors: arr(o, "errors", "import", (e, p) => {
      const eo = obj(e, p);
      return { row: int(eo, "row", p), message: str(eo, "message", p) };
    }),
  };
}

export async function fetchRuns(datasetId: string | null, signal?: AbortSignal) {
  const qs = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : "";
  return (
    await requestJson(
      `/api/v1/evaluations/runs${qs}`,
      (raw) => (Array.isArray(raw) ? raw.map((r, i) => parseRun(r, `runs[${i}]`)) : []),
      { signal },
    )
  ).data;
}

export async function fetchRun(id: string, signal?: AbortSignal) {
  return (
    await requestJson(
      `/api/v1/evaluations/runs/${encodeURIComponent(id)}`,
      (raw) => {
        const run = parseRun(raw);
        return {
          ...run,
          results: arr(obj(raw, "run"), "results", "run", parseResult),
        } satisfies RunDetail;
      },
      { signal },
    )
  ).data;
}

export async function startRun(datasetId: string, config: RunConfig) {
  return (
    await requestJson("/api/v1/evaluations/runs", (r) => parseRun(r), {
      method: "POST",
      json: { dataset_id: datasetId, config },
    })
  ).data;
}

export async function deleteRun(id: string) {
  await requestJson(`/api/v1/evaluations/runs/${encodeURIComponent(id)}`, () => undefined, {
    method: "DELETE",
  });
}

export function exportUrl(id: string, format: "json" | "csv") {
  return `/api/v1/evaluations/runs/${encodeURIComponent(id)}/export?format=${format}`;
}

export { ApiError };
