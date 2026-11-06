import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SystemStatusProvider } from "@/components/system-status/system-status-provider";
import { TooltipProvider } from "@/components/ui/tooltip";
import { RAW_DOC, RAW_POLICY } from "@/test/fixtures";

import { LibraryView } from "./library-view";

const READY_DOC = {
  ...RAW_DOC,
  id: "d2",
  original_name: "Handbook.md",
  file_type: "md",
  status: "ready",
  chunk_count: 4,
  citation_granularity: "section",
  latest_job: { ...RAW_DOC.latest_job, id: "j2", document_id: "d2", status: "succeeded" },
};

const FAILED_DOC = {
  ...RAW_DOC,
  id: "d3",
  original_name: "Scan.pdf",
  status: "failed",
  last_error: { code: "no_text_layer", message: "No text could be extracted." },
  latest_job: { ...RAW_DOC.latest_job, id: "j3", document_id: "d3", status: "failed" },
};

function readiness(workerState: "ok" | "missing") {
  return {
    status: "degraded",
    checks: [
      { name: "postgres", state: "ok", required: true, detail: "PostgreSQL 16" },
      {
        name: "ingestion_worker",
        state: workerState,
        required: false,
        detail: "worker",
        remediation: workerState === "ok" ? null : "./scripts/dev.ps1 worker",
      },
    ],
  };
}

function stubApi(
  documents: unknown[],
  opts: { failDocuments?: boolean; worker?: "ok" | "missing" } = {},
) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("/health/ready")) return Response.json(readiness(opts.worker ?? "ok"));
    if (url.includes("upload-policy")) return Response.json(RAW_POLICY);
    if (url.endsWith("/retry") && init?.method === "POST") {
      return Response.json({ ...FAILED_DOC, status: "queued", last_error: null }, { status: 202 });
    }
    if (url.includes("/extraction")) {
      return Response.json({
        total_sections: 1,
        sections: [{ ordinal: 0, page_number: null, section_path: "Leave", text: "24 days" }],
      });
    }
    if (url.includes("/chunks")) {
      return Response.json({
        items: [
          {
            id: "c1",
            document_id: "d2",
            strategy: "recursive",
            chunk_index: 0,
            text: "Employees receive 24 days.",
            page_start: null,
            page_end: null,
            section_path: "Handbook > Leave",
            char_count: 26,
            token_count: 7,
            content_hash: "ab".repeat(32),
          },
        ],
        total: 1,
        limit: 10,
        offset: 0,
      });
    }
    if (opts.failDocuments) {
      return Response.json(
        {
          error: {
            code: "schema_not_migrated",
            message: "The database schema is not up to date.",
            request_id: "req-1",
          },
        },
        { status: 503 },
      );
    }
    const ready = url.includes("status=ready");
    const items = ready
      ? documents.filter((d) => (d as { status: string }).status === "ready")
      : documents;
    return Response.json({ items, total: items.length, limit: 25, offset: 0 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const renderView = () =>
  render(
    <SystemStatusProvider>
      <TooltipProvider>
        <LibraryView />
      </TooltipProvider>
    </SystemStatusProvider>,
  );

afterEach(() => vi.unstubAllGlobals());

describe("LibraryView", () => {
  it("shows an empty state with an upload action", async () => {
    stubApi([]);
    renderView();
    expect(await screen.findByText("No documents yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Upload your first document/ })).toBeEnabled();
    expect(screen.getByText(/0 documents · 0 indexed/)).toBeInTheDocument();
  });

  it("lists documents with their status and indexed count", async () => {
    stubApi([RAW_DOC, READY_DOC]);
    renderView();
    const row = (await screen.findByText("Leave Policy.pdf")).closest("tr")!;
    expect(within(row).getByText(/Queued/)).toBeInTheDocument();
    expect(screen.getByText(/2 documents · 1 indexed/)).toBeInTheDocument();
  });

  it("warns with the exact command when documents are queued but no worker runs", async () => {
    stubApi([RAW_DOC], { worker: "missing" });
    renderView();
    expect(await screen.findByText("Ingestion worker not running")).toBeInTheDocument();
    expect(screen.getByText("./scripts/dev.ps1 worker")).toBeInTheDocument();
  });

  it("does not warn about the worker when nothing is waiting", async () => {
    stubApi([READY_DOC], { worker: "missing" });
    renderView();
    await screen.findByText("Handbook.md");
    expect(screen.queryByText("Ingestion worker not running")).not.toBeInTheDocument();
  });

  it("retries a failed document from its row", async () => {
    const fetchMock = stubApi([FAILED_DOC]);
    renderView();
    const row = (await screen.findByText("Scan.pdf")).closest("tr")!;
    expect(within(row).getByText("No text could be extracted.")).toBeInTheDocument();
    await userEvent.click(within(row).getByRole("button", { name: /Retry processing Scan.pdf/ }));
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) => String(url).endsWith("/d3/retry") && init?.method === "POST",
      ),
    ).toBe(true);
  });

  it("opens the detail drawer with extraction preview and chunks", async () => {
    stubApi([READY_DOC]);
    renderView();
    await userEvent.click(await screen.findByRole("button", { name: "Handbook.md" }));
    const drawer = await screen.findByRole("dialog");
    expect(within(drawer).getByText("Extraction preview")).toBeInTheDocument();
    expect(await within(drawer).findByText("Employees receive 24 days.")).toBeInTheDocument();
    expect(within(drawer).getByText(/citations point to headings/)).toBeInTheDocument();
    expect(within(drawer).getByRole("button", { name: "Fixed-size" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("shows a recoverable error with the exact fix command", async () => {
    stubApi([], { failDocuments: true });
    renderView();
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("./scripts/dev.ps1 migrate")).toBeInTheDocument();
    expect(within(alert).getByText(/req-1/)).toBeInTheDocument();
    expect(within(alert).getByRole("button", { name: /Try again/ })).toBeInTheDocument();
  });
});
