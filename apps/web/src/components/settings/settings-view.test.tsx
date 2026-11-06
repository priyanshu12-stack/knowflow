import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SystemStatusProvider } from "@/components/system-status/system-status-provider";

import { SettingsView } from "./settings-view";

const SETTINGS = {
  runtime: { reachable: true, version: "0.17.1", base_url: "http://127.0.0.1:11434", error: null },
  installed: [
    {
      name: "qwen3:4b",
      digest: "359d",
      size_bytes: 2_497_293_931,
      family: "qwen3",
      parameter_size: "4.0B",
      quantization: "Q4_K_M",
      kind: "generation",
    },
    {
      name: "nomic-embed-text:v1.5",
      digest: "0a10",
      size_bytes: 274_302_450,
      family: "nomic-bert",
      parameter_size: "137M",
      quantization: "F16",
      kind: "embedding",
    },
    {
      name: "mxbai-embed-large:latest",
      digest: "aaaa",
      size_bytes: 669_000_000,
      family: "bert",
      parameter_size: "334M",
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
    note: "Not installed. Basic and hybrid search work without it.",
  },
  active_embedding: {
    model: "nomic-embed-text:v1.5",
    digest: "0a10",
    dimension: 768,
    created_at: "2026-11-07T00:00:00Z",
  },
  documents_needing_reindex: 0,
  setup_commands: ['pip install -e "apps/api[reranker]"   # optional, ~2.3 GB'],
};

function stub(overrides: Record<string, unknown> = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("/health/ready")) return Response.json({ status: "ready", checks: [] });
    if (url.endsWith("/settings/models/validate")) {
      return Response.json({
        ok: true,
        checks: [
          { name: "runtime", state: "ok", detail: "Ollama is reachable.", latency_ms: null },
          {
            name: "embedding_model",
            state: "ok",
            detail: "Returns 768-dimensional vectors.",
            latency_ms: 40,
          },
          {
            name: "generation_model",
            state: "ok",
            detail: "Returned valid structured JSON.",
            latency_ms: 4200,
          },
        ],
        embedding_dimension: 768,
        embedding_model_changed: false,
      });
    }
    if (url.endsWith("/settings/models") && init?.method === "PUT") {
      return Response.json({ settings: SETTINGS, reembed_required: false });
    }
    return Response.json({ ...SETTINGS, ...overrides });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const renderView = () =>
  render(
    <SystemStatusProvider>
      <SettingsView />
    </SystemStatusProvider>,
  );

afterEach(() => vi.unstubAllGlobals());

describe("SettingsView", () => {
  it("shows runtime status, installed models and the active embedding space", async () => {
    stub();
    renderView();
    expect(await screen.findByText("Ollama 0.17.1")).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Installed local models" });
    expect(within(table).getByText("qwen3:4b")).toBeInTheDocument();
    expect(within(table).getByText("Q4_K_M")).toBeInTheDocument();
    expect(screen.getByText("768")).toBeInTheDocument();
    // DRD §7.6: no provider cards or API-key fields.
    expect(screen.queryByLabelText(/api key/i)).toBeNull();
    expect(document.querySelector("input[type=password]")).toBeNull();
  });

  it("disables the reranker with a reason when it isn't installed", async () => {
    stub();
    renderView();
    const box = await screen.findByLabelText(/Reranker/);
    expect(box).toBeDisabled();
    expect(screen.getByText(/Basic and hybrid search work without it/)).toBeInTheDocument();
  });

  it("warns strongly before switching the embedding model", async () => {
    stub();
    renderView();
    const select = await screen.findByLabelText(/Embedding model/);
    await userEvent.selectOptions(select, "mxbai-embed-large:latest");
    expect(screen.getByRole("alert")).toHaveTextContent(/re-indexed/);
    expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
  });

  it("validates the configuration and shows each probe result", async () => {
    stub();
    renderView();
    await userEvent.click(await screen.findByRole("button", { name: /Validate configuration/ }));
    expect(await screen.findByText("Configuration works")).toBeInTheDocument();
    expect(screen.getByText(/768-dimensional/)).toBeInTheDocument();
    expect(screen.getByText("4200 ms")).toBeInTheDocument();
  });

  it("shows the exact command when Ollama is not running", async () => {
    stub({
      runtime: {
        reachable: false,
        version: null,
        base_url: "http://127.0.0.1:11434",
        error: "Cannot reach the local Ollama runtime.",
      },
      installed: [],
    });
    renderView();
    expect(await screen.findByText("Ollama unreachable")).toBeInTheDocument();
    expect(screen.getByText("ollama serve")).toBeInTheDocument();
  });

  it("offers re-indexing when documents use an old embedding space", async () => {
    stub({ documents_needing_reindex: 3 });
    renderView();
    expect(await screen.findByText("3 documents need re-indexing.")).toBeInTheDocument();
  });
});
