import type { Page, Route } from "@playwright/test";

/** Realistic API payloads (same shapes the FastAPI contracts return). */
const NOW = "2026-11-07T10:00:00Z";

const DOC = {
  id: "d1",
  original_name: "travel-and-expenses-policy.md",
  file_type: "md",
  mime_type: "text/markdown",
  size_bytes: 2048,
  sha256: "ab".repeat(32),
  version: 1,
  status: "ready",
  page_count: null,
  chunk_count: 6,
  extracted_char_count: 1980,
  citation_granularity: "section",
  last_error: null,
  latest_job: null,
  created_at: NOW,
  updated_at: NOW,
};

const CITATION = {
  number: 1,
  chunk_id: "c1",
  document_id: "d1",
  document_name: "travel-and-expenses-policy.md",
  page_start: null,
  page_end: null,
  section_path: "Travel and Expenses Policy > Accommodation",
  excerpt: "Hotels are capped at 150 EUR per night in most cities.",
};

const TRACE = {
  mode: "dense",
  strategy: "recursive",
  top_k: 6,
  candidates: 6,
  sources_supplied: 4,
  reranked: false,
  timings_ms: { embed_query: 40, dense: 2, generation: 41000 },
  candidate_ranks: [],
};

const ANSWER_MSG = {
  id: "m2",
  role: "assistant",
  content: "Hotels are capped at 150 EUR per night in most cities [1].",
  citations: [CITATION],
  metadata: {
    abstained: false,
    retrieval: TRACE,
    model: "qwen3:4b",
    prompt_version: "rag-answer-v2",
    latency_ms: 41500,
  },
  feedback: null,
  created_at: NOW,
};

const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

export async function mockApi(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/v1", "");
    const method = route.request().method();

    if (path === "/health/ready")
      return json(route, {
        status: "ready",
        checks: [
          { name: "postgres", state: "ok", required: true, detail: "PostgreSQL 16.15" },
          { name: "pgvector", state: "ok", required: true, detail: "pgvector 0.8.6" },
          {
            name: "database_schema",
            state: "ok",
            required: true,
            detail: "Schema at revision 0007.",
          },
          { name: "ollama", state: "ok", required: true, detail: "Ollama 0.17.1" },
          {
            name: "generation_model",
            state: "ok",
            required: false,
            detail: "qwen3:4b is installed.",
          },
          {
            name: "embedding_model",
            state: "ok",
            required: false,
            detail: "nomic-embed-text:v1.5 is installed.",
          },
          {
            name: "ingestion_worker",
            state: "ok",
            required: false,
            detail: "Ingestion worker running (pid 1).",
          },
        ],
      });
    if (path === "/workspaces/current")
      return json(route, {
        id: "w1",
        name: "Northwind demo",
        is_default: true,
        created_at: NOW,
        updated_at: NOW,
      });
    if (path === "/documents/upload-policy")
      return json(route, {
        max_bytes: 26214400,
        formats: [
          {
            file_type: "pdf",
            label: "PDF (text-based)",
            mime_type: "application/pdf",
            extensions: [".pdf"],
          },
          { file_type: "md", label: "Markdown", mime_type: "text/markdown", extensions: [".md"] },
        ],
      });
    if (path === "/documents") return json(route, { items: [DOC], total: 1, limit: 25, offset: 0 });
    if (path === "/conversations" && method === "GET")
      return json(route, { items: [], total: 0, limit: 100, offset: 0 });
    if (path === "/chat/query")
      return json(route, {
        conversation_id: "conv1",
        message_id: "m2",
        answer: ANSWER_MSG.content,
        citations: [CITATION],
        abstained: false,
        abstain_reason: null,
        retrieval: TRACE,
        model: "qwen3:4b",
        prompt_version: "rag-answer-v2",
        latency_ms: 41500,
        request_id: "req-1",
      });
    if (path === "/conversations/conv1")
      return json(route, {
        id: "conv1",
        title: "hotel cap",
        created_at: NOW,
        updated_at: NOW,
        message_count: 2,
        messages: [
          {
            id: "m1",
            role: "user",
            content: "What is the hotel cap?",
            citations: [],
            metadata: {},
            feedback: null,
            created_at: NOW,
          },
          ANSWER_MSG,
        ],
      });
    if (path === "/activity/summary")
      return json(route, {
        documents: 1,
        documents_ready: 1,
        documents_processing: 0,
        documents_failed: 0,
        chunks: 6,
        questions_7d: 1,
        abstained_7d: 0,
        answer_latency_p50_ms: 41500,
        sql_questions_7d: 0,
        latest_evaluation: null,
      });
    if (path === "/activity/events") return json(route, { total: 0, items: [] });
    if (path === "/activity/jobs") return json(route, []);
    if (path === "/settings/models")
      return json(route, {
        runtime: {
          reachable: true,
          version: "0.17.1",
          base_url: "http://127.0.0.1:11434",
          error: null,
        },
        installed: [
          {
            name: "qwen3:4b",
            digest: "359d",
            size_bytes: 2497293931,
            family: "qwen3",
            parameter_size: "4.0B",
            quantization: "Q4_K_M",
            kind: "generation",
          },
          {
            name: "nomic-embed-text:v1.5",
            digest: "0a10",
            size_bytes: 274302450,
            family: "nomic-bert",
            parameter_size: "137M",
            quantization: "F16",
            kind: "embedding",
          },
        ],
        generation_model: "qwen3:4b",
        embedding_model: "nomic-embed-text:v1.5",
        reranker: {
          enabled: false,
          available: false,
          model: "BAAI/bge-reranker-v2-m3",
          note: "Not installed.",
        },
        active_embedding: {
          model: "nomic-embed-text:v1.5",
          digest: "0a10",
          dimension: 768,
          created_at: NOW,
        },
        documents_needing_reindex: 0,
        setup_commands: [],
      });
    // A dataset with one finished run, so the wide (scrolling) runs table is part of the
    // overflow checks: its sr-only header once escaped the scroll box and widened the page.
    if (path === "/evaluations/datasets")
      return json(route, [
        {
          id: "ds1",
          name: "Northwind gold set",
          version: "v1",
          description: null,
          created_at: NOW,
          cases: 50,
          dev_cases: 38,
          test_cases: 12,
          runs: 1,
          missing_documents: [],
        },
      ]);
    if (path === "/evaluations/runs")
      return json(route, [
        {
          id: "r1",
          dataset_id: "ds1",
          label: "S3 recursive + hybrid (RRF) + answers",
          strategy: "S3",
          model_id: "nomic-embed-text:v1.5@0a10",
          status: "succeeded",
          progress: 50,
          total: 50,
          config: { mode: "hybrid", split: "all", top_k: 5, preset: "S3", rerank: false },
          aggregate_metrics: {
            mrr: 0.875,
            cases: 50,
            errors: 0,
            hit_at_k: 1.0,
            ndcg_at_k: 0.9077,
            recall_at_k: 1.0,
            precision_at_k: 0.2,
            retrieval_cases: 40,
            retrieval_ms_p50: 536.0,
            retrieval_ms_p95: 1145.9,
            abstention_correct: 1.0,
            abstention_correct_n: 50,
            citation_precision: 0.75,
            citation_precision_n: 40,
            injection_resisted: 1.0,
            injection_resisted_n: 1,
            failure_categories: {},
          },
          error: null,
          created_at: NOW,
          started_at: NOW,
          completed_at: NOW,
        },
      ]);
    if (path === "/sql/connections")
      return json(route, [
        {
          id: "s1",
          display_name: "Demo sales (synthetic)",
          db_type: "postgresql",
          host: "localhost",
          port: 5432,
          database_name: "knowflow_demo",
          username: "knowflow_reader",
          allowed_schemas: ["sales"],
          is_demo: true,
          created_at: NOW,
        },
      ]);
    if (path === "/sql/schema/s1")
      return json(route, {
        connection: {},
        tables: [
          {
            schema_name: "sales",
            name: "customers",
            description: "Synthetic customers.",
            columns: [{ name: "name", data_type: "text", nullable: false, description: null }],
          },
        ],
        glossary: [],
        max_rows: 500,
        statement_timeout_ms: 5000,
      });
    return json(
      route,
      { error: { code: "not_mocked", message: `No mock for ${method} ${path}`, request_id: null } },
      404,
    );
  });
}
