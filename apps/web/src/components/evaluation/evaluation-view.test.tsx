import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EvaluationView } from "./evaluation-view";

const DATASET = {
  id: "ds1",
  name: "Northwind gold set",
  version: "v1",
  description: "Synthetic sample",
  created_at: "2026-11-07T00:00:00Z",
  cases: 50,
  dev_cases: 38,
  test_cases: 12,
  runs: 1,
  missing_documents: [],
};

const RUN = {
  id: "r1",
  dataset_id: "ds1",
  label: "S3 recursive + hybrid (RRF)",
  strategy: "S3",
  model_id: "nomic-embed-text:v1.5@0a109f422b47",
  status: "succeeded",
  progress: 50,
  total: 50,
  config: {
    top_k: 5,
    split: "all",
    embedding: { model: "nomic-embed-text:v1.5", dimension: 768 },
    machine: { cpu_count: 12, ram_total_gb: 7.3 },
  },
  aggregate_metrics: {
    cases: 50,
    retrieval_cases: 47,
    recall_at_k: 0.968,
    precision_at_k: 0.196,
    mrr: 0.891,
    ndcg_at_k: 0.905,
    abstention_correct: null,
    abstention_correct_n: 0,
    citation_precision: null,
    citation_precision_n: 0,
    retrieval_ms_p50: 42,
    retrieval_ms_p95: 50,
    failure_categories: { evidence_not_retrieved: 1 },
  },
  error: null,
  created_at: "2026-11-07T00:00:00Z",
  started_at: null,
  completed_at: "2026-11-07T00:01:00Z",
};

const RESULT = {
  case_id: "c1",
  external_id: "q13",
  split: "dev",
  question: "What is the policy ID of the travel policy?",
  reference_answer: "FIN-TE-07.",
  answerable: true,
  expected_evidence: [{ document: "travel-and-expenses-policy.md", quote: "Policy ID FIN-TE-07" }],
  tags: ["exact-term"],
  retrieved: [
    {
      chunk_id: "k1",
      document_name: "travel-and-expenses-policy.md",
      page_start: null,
      page_end: null,
      section_path: "Travel and Expenses Policy",
      score: 0.03,
      ranks: { dense: 2, lexical: 1 },
      relevant: true,
      excerpt: "Policy owner: Finance. Policy ID FIN-TE-07.",
    },
  ],
  answer: null,
  metrics: { recall_at_k: 1, mrr: 1 },
  failure_category: null,
  latency_ms: 40,
  error: null,
};

function stub({ datasets = [DATASET], reranker = false } = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("/settings/models")) {
      return Response.json({
        runtime: { reachable: true, version: "x", base_url: "u", error: null },
        installed: [],
        generation_model: "qwen3:4b",
        embedding_model: "nomic",
        reranker: { enabled: false, available: reranker, model: "bge", note: "n" },
        active_embedding: null,
        documents_needing_reindex: 0,
        setup_commands: [],
      });
    }
    if (url.endsWith("/evaluations/datasets")) return Response.json(datasets);
    if (url.endsWith("/evaluations/runs") && init?.method === "POST") {
      return Response.json({ ...RUN, id: "r2", status: "queued", progress: 0 }, { status: 202 });
    }
    if (url.includes("/evaluations/runs/r1")) return Response.json({ ...RUN, results: [RESULT] });
    if (url.includes("/evaluations/runs")) return Response.json([RUN]);
    return Response.json({});
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => vi.unstubAllGlobals());

describe("EvaluationView", () => {
  it("offers the sample set when no dataset exists", async () => {
    stub({ datasets: [] });
    render(<EvaluationView />);
    await userEvent.click(await screen.findByText("Add a dataset"));
    expect(
      screen.getByRole("button", { name: /Load sample documents and gold set/ }),
    ).toBeEnabled();
    expect(screen.getByRole("button", { name: /Import CSV or JSONL/ })).toBeDisabled();
  });

  it("shows runs as a comparison table with sample counts", async () => {
    stub();
    render(<EvaluationView />);
    const table = await screen.findByRole("table", { name: "Evaluation runs and their metrics" });
    const row = within(table).getByText("S3 recursive + hybrid (RRF)").closest("tr")!;
    expect(within(row).getByText("0.968")).toBeInTheDocument();
    expect(within(row).getAllByText("n=47").length).toBeGreaterThan(0);
    expect(within(row).getByText("42 ms / 50 ms")).toBeInTheDocument();
    expect(within(row).getByRole("link", { name: /Export .* as CSV/ })).toHaveAttribute(
      "href",
      "/api/v1/evaluations/runs/r1/export?format=csv",
    );
  });

  it("disables S4 with a reason when the reranker isn't installed", async () => {
    stub();
    render(<EvaluationView />);
    const s4 = await screen.findByRole("radio", { name: /S4/ });
    expect(s4).toBeDisabled();
    expect(screen.getByText(/Needs the optional reranker/)).toBeInTheDocument();
  });

  it("starts a run with the chosen strategy and warns before generating answers", async () => {
    const fetchMock = stub();
    render(<EvaluationView />);
    await userEvent.click(await screen.findByRole("radio", { name: /S1/ }));
    await userEvent.click(screen.getByLabelText("Also generate answers"));
    expect(screen.getByRole("note")).toHaveTextContent(/30–90 seconds per case/);
    await userEvent.click(screen.getByRole("button", { name: /Run evaluation/ }));
    const call = fetchMock.mock.calls.find(
      ([u, i]) => String(u).endsWith("/evaluations/runs") && i?.method === "POST",
    );
    expect(JSON.parse(String(call![1]!.body))).toMatchObject({
      dataset_id: "ds1",
      config: { preset: "S1", top_k: 5, split: "all", generate_answers: true },
    });
  });

  it("inspects a case: expected evidence next to retrieved passages", async () => {
    stub();
    render(<EvaluationView />);
    await userEvent.click(
      await screen.findByRole("button", { name: "S3 recursive + hybrid (RRF)" }),
    );
    expect(await screen.findByText(/768-d/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: RESULT.question }));
    const inspector = screen.getByLabelText("Case q13");
    expect(within(inspector).getByText(/“Policy ID FIN-TE-07”/)).toBeInTheDocument();
    expect(within(inspector).getByText("Relevant.")).toBeInTheDocument();
    expect(within(inspector).getByText("dense 2 · lexical 1")).toBeInTheDocument();
  });
});
