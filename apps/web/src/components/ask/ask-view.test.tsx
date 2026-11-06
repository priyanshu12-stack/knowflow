import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SystemStatusProvider } from "@/components/system-status/system-status-provider";
import { TooltipProvider } from "@/components/ui/tooltip";
import { RAW_DOC } from "@/test/fixtures";

import { AnswerText } from "./answer-text";
import { AskView } from "./ask-view";

const READY = { ...RAW_DOC, status: "ready", original_name: "travel.pdf", chunk_count: 3 };

const CITATION = {
  number: 1,
  chunk_id: "c1",
  document_id: "d1",
  document_name: "travel.pdf",
  page_start: 2,
  page_end: 2,
  section_path: null,
  excerpt: "Hotels are capped at 150 EUR per night.",
};

const TRACE = {
  mode: "dense",
  strategy: "recursive",
  top_k: 6,
  candidates: 6,
  sources_supplied: 4,
  timings_ms: { embed_query: 1200, dense: 40, generation: 54000 },
  candidate_ranks: [],
};

function conversation(messages: unknown[]) {
  return {
    id: "conv1",
    title: "hotel cap",
    created_at: "2026-11-07T00:00:00Z",
    updated_at: "2026-11-07T00:00:00Z",
    message_count: messages.length,
    messages,
  };
}

const USER_MSG = {
  id: "m1",
  role: "user",
  content: "What is the hotel cap?",
  citations: [],
  metadata: {},
  feedback: null,
  created_at: "2026-11-07T00:00:00Z",
};

const ANSWER_MSG = {
  id: "m2",
  role: "assistant",
  content: "Hotels are capped at 150 EUR per night [1].",
  citations: [CITATION],
  metadata: {
    abstained: false,
    retrieval: TRACE,
    model: "qwen3:4b",
    prompt_version: "rag-answer-v2",
    latency_ms: 55300,
  },
  feedback: null,
  created_at: "2026-11-07T00:00:01Z",
};

function stub({
  docs = [READY],
  generation = "ok",
}: { docs?: unknown[]; generation?: string } = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("/health/ready")) {
      return Response.json({
        status: "ready",
        checks: [
          {
            name: "generation_model",
            state: generation,
            required: false,
            detail: "qwen3:4b is not installed.",
            remediation: generation === "ok" ? null : "ollama pull qwen3:4b",
          },
        ],
      });
    }
    if (url.includes("/documents")) {
      return Response.json({ items: docs, total: docs.length, limit: 100, offset: 0 });
    }
    if (url.endsWith("/chat/query")) {
      return Response.json({
        conversation_id: "conv1",
        message_id: "m2",
        answer: ANSWER_MSG.content,
        citations: [CITATION],
        abstained: false,
        abstain_reason: null,
        retrieval: TRACE,
        model: "qwen3:4b",
        prompt_version: "rag-answer-v2",
        latency_ms: 55300,
        request_id: "r1",
      });
    }
    if (url.includes("/feedback") && init?.method === "PUT")
      return new Response(null, { status: 204 });
    if (url.endsWith("/conversations/conv1"))
      return Response.json(conversation([USER_MSG, ANSWER_MSG]));
    if (url.includes("/conversations"))
      return Response.json({ items: [], total: 0, limit: 100, offset: 0 });
    return Response.json({});
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const renderView = () =>
  render(
    <SystemStatusProvider>
      <TooltipProvider>
        <AskView />
      </TooltipProvider>
    </SystemStatusProvider>,
  );

afterEach(() => vi.unstubAllGlobals());

describe("AnswerText", () => {
  it("turns markers into citation chips and ignores unknown ones", async () => {
    const onSelect = vi.fn();
    render(
      <AnswerText
        text={"Hotels are **capped** at 150 EUR [1] [7].\n\n- one [1]\n- two"}
        citations={[
          {
            number: 1,
            chunkId: "c",
            documentId: "d",
            documentName: "travel.pdf",
            pageStart: 2,
            pageEnd: 2,
            sectionPath: null,
            excerpt: "x",
          },
        ]}
        selected={null}
        onSelect={onSelect}
      />,
    );
    const chips = screen.getAllByRole("button", { name: "Source 1: travel.pdf" });
    expect(chips).toHaveLength(2);
    expect(screen.queryByText("[7]")).toBeNull();
    expect(screen.getByText("capped").tagName).toBe("STRONG");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    await userEvent.click(chips[0]);
    expect(onSelect).toHaveBeenCalledOnce();
  });

  it("never renders model text as HTML", () => {
    render(
      <AnswerText
        text={'<img src=x onerror="alert(1)"> hi'}
        citations={[]}
        selected={null}
        onSelect={() => {}}
      />,
    );
    expect(document.querySelector("img")).toBeNull();
    expect(screen.getByText(/<img/)).toBeInTheDocument();
  });
});

describe("AskView", () => {
  it("asks a question and shows the cited answer with its source drawer", async () => {
    const fetchMock = stub();
    renderView();
    const box = await screen.findByLabelText("Your question");
    await userEvent.type(box, "What is the hotel cap?");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));

    const answer = await screen.findByRole("article", { name: "Answer" });
    expect(within(answer).getByText(/Hotels are capped at 150 EUR per night/)).toBeInTheDocument();
    expect(within(answer).getByText(/Searched 6 passages, used 4/)).toBeInTheDocument();
    expect(within(answer).getByText(/page 2/)).toBeInTheDocument();

    const body = JSON.parse(
      String(fetchMock.mock.calls.find(([u]) => String(u).endsWith("/chat/query"))![1]!.body),
    );
    expect(body).toMatchObject({
      question: "What is the hotel cap?",
      retrieval_config: { mode: "dense" },
    });

    await userEvent.click(
      within(answer).getAllByRole("button", { name: "Source 1: travel.pdf" })[0],
    );
    const drawer = await screen.findByRole("dialog");
    expect(within(drawer).getByText("Hotels are capped at 150 EUR per night.")).toBeInTheDocument();
    expect(within(drawer).getByRole("link", { name: /Open document in Library/ })).toHaveAttribute(
      "href",
      "/library?document=d1",
    );
  });

  it("shows retrieval details when toggled", async () => {
    stub();
    renderView();
    await userEvent.type(await screen.findByLabelText("Your question"), "hotel cap");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    await screen.findByRole("article", { name: "Answer" });
    await userEvent.click(screen.getByLabelText("Show retrieval details"));
    expect(screen.getByText("How this was found")).toBeInTheDocument();
    expect(screen.getByText("rag-answer-v2")).toBeInTheDocument();
    expect(screen.getByText("54 s")).toBeInTheDocument();
  });

  it("records not-helpful feedback with a reason", async () => {
    const fetchMock = stub();
    renderView();
    await userEvent.type(await screen.findByLabelText("Your question"), "hotel cap");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    await screen.findByRole("article", { name: "Answer" });
    await userEvent.click(screen.getByRole("button", { name: "Not helpful" }));
    await userEvent.type(screen.getByLabelText(/What was wrong/), "wrong page");
    await userEvent.click(screen.getByRole("button", { name: "Send feedback" }));
    const call = fetchMock.mock.calls.find(([u]) => String(u).includes("/messages/m2/feedback"));
    expect(JSON.parse(String(call![1]!.body))).toEqual({
      rating: "not_helpful",
      reason: "wrong page",
    });
  });

  it("explains what to do when nothing is indexed", async () => {
    stub({ docs: [] });
    renderView();
    expect(await screen.findByText("No indexed documents yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Knowledge Library" })).toHaveAttribute(
      "href",
      "/library",
    );
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
  });

  it("shows the pull command when the generation model is missing", async () => {
    stub({ generation: "missing" });
    renderView();
    expect(await screen.findByText("Generation model not installed")).toBeInTheDocument();
    expect(screen.getByText("ollama pull qwen3:4b")).toBeInTheDocument();
  });
});
