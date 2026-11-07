import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HelpView } from "@/components/help/help-view";
import { OverviewDashboard } from "@/components/overview/overview-dashboard";

import { ActivityView } from "./activity-view";

const EVENTS = {
  total: 2,
  items: [
    {
      id: "e1",
      created_at: "2026-11-07T10:00:00Z",
      actor: "worker",
      action: "ingestion.failed",
      resource_type: "document",
      resource_id: "d1",
      request_id: null,
      metadata: { error_code: "no_text_layer" },
    },
    {
      id: "e2",
      created_at: "2026-11-07T09:00:00Z",
      actor: "local-user",
      action: "chat.answered",
      resource_type: "message",
      resource_id: "m1",
      request_id: "req-42",
      metadata: { abstained: false, citations: 2, latency_ms: 55300 },
    },
  ],
};

const JOBS = [
  {
    id: "j1",
    document_id: "d1",
    document_name: "scan.pdf",
    status: "failed",
    stage: null,
    attempts: 1,
    error_code: "no_text_layer",
    error_message: "No text could be extracted.",
    created_at: "2026-11-07T10:00:00Z",
    started_at: "2026-11-07T10:00:00Z",
    completed_at: "2026-11-07T10:00:02Z",
    duration_ms: 1700,
  },
];

const SUMMARY = {
  documents: 6,
  documents_ready: 5,
  documents_processing: 0,
  documents_failed: 1,
  chunks: 31,
  questions_7d: 4,
  abstained_7d: 1,
  answer_latency_p50_ms: 55000,
  sql_questions_7d: 2,
  latest_evaluation: {
    id: "r1",
    label: "S3 recursive + hybrid (RRF)",
    status: "succeeded",
    recall_at_k: 0.968,
    mrr: 0.891,
    cases: 50,
    created_at: "2026-11-07T00:00:00Z",
  },
};

function stub() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/activity/events")) {
      const category = new URL(url, "http://x").searchParams.get("category");
      return Response.json(
        category === "ingestion" ? { total: 1, items: [EVENTS.items[0]] } : EVENTS,
      );
    }
    if (url.includes("/activity/jobs")) return Response.json(JOBS);
    if (url.includes("/activity/summary")) return Response.json(SUMMARY);
    return Response.json({});
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => vi.unstubAllGlobals());

describe("ActivityView", () => {
  it("lists events in plain language with request ids and filters by category", async () => {
    const fetchMock = stub();
    render(<ActivityView />);
    const table = await screen.findByRole("table", { name: "Audit events" });
    expect(within(table).getByText("Processing failed (no_text_layer)")).toBeInTheDocument();
    expect(within(table).getByText("Answered a question with 2 citation(s)")).toBeInTheDocument();
    expect(within(table).getByText("req-42")).toBeInTheDocument();
    expect(within(table).getByText("55.3 s")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Ingestion" }));
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes("category=ingestion"))).toBe(true);
  });

  it("shows ingestion jobs with errors and a link to the document", async () => {
    stub();
    render(<ActivityView />);
    await userEvent.click(screen.getByRole("tab", { name: "Ingestion jobs" }));
    const table = await screen.findByRole("table", { name: "Ingestion jobs" });
    expect(within(table).getByRole("link", { name: "scan.pdf" })).toHaveAttribute(
      "href",
      "/library?document=d1",
    );
    expect(within(table).getByText(/No text could be extracted/)).toBeInTheDocument();
    expect(within(table).getByText("1.7 s")).toBeInTheDocument();
  });
});

describe("OverviewDashboard", () => {
  it("shows only real metrics, recent activity and working quick actions", async () => {
    stub();
    render(<OverviewDashboard />);
    expect(await screen.findByText("Documents indexed")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText(/0 processing · 1 failed/)).toBeInTheDocument();
    expect(screen.getByText("R 0.97")).toBeInTheDocument();
    expect(await screen.findByText("Processing failed (no_text_layer)")).toBeInTheDocument();
    for (const [name, href] of [
      ["Upload documents", "/library"],
      ["Ask a question", "/ask"],
      ["Run an evaluation", "/evaluation"],
    ]) {
      expect(screen.getByRole("link", { name })).toHaveAttribute("href", href);
    }
  });
});

describe("HelpView", () => {
  it("lists setup commands and troubleshooting fixes", () => {
    render(<HelpView />);
    expect(screen.getAllByText("./scripts/dev.ps1 worker").length).toBeGreaterThan(0);
    expect(screen.getByText("Documents stay Queued")).toBeInTheDocument();
    expect(screen.getByText(/OCR isn't supported/)).toBeInTheDocument();
  });
});
