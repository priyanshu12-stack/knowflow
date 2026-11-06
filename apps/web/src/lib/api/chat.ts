import { requestJson } from "./client";
import { arr, bool, int, nullableInt, nullableStr, obj, str, type Obj } from "./validate";

export type RetrievalMode = "dense" | "lexical" | "hybrid";

export interface Citation {
  number: number;
  chunkId: string;
  documentId: string;
  documentName: string;
  pageStart: number | null;
  pageEnd: number | null;
  sectionPath: string | null;
  excerpt: string;
}

export interface RetrievalTrace {
  mode: string;
  strategy: string;
  topK: number;
  candidates: number;
  sourcesSupplied: number;
  timingsMs: Record<string, number>;
}

export interface Answer {
  conversationId: string;
  messageId: string;
  answer: string;
  citations: Citation[];
  abstained: boolean;
  abstainReason: string | null;
  retrieval: RetrievalTrace;
  model: string | null;
  promptVersion: string;
  latencyMs: number;
  requestId: string | null;
}

export interface ConversationSummary {
  id: string;
  title: string;
  updatedAt: string;
  messageCount: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  abstained: boolean;
  retrieval: RetrievalTrace | null;
  model: string | null;
  promptVersion: string | null;
  latencyMs: number | null;
  feedback: { rating: "helpful" | "not_helpful"; reason: string | null } | null;
  createdAt: string;
}

export interface ConversationDetail extends ConversationSummary {
  messages: ChatMessage[];
}

export function parseCitation(raw: unknown, p: string): Citation {
  const o = obj(raw, p);
  return {
    number: int(o, "number", p),
    chunkId: str(o, "chunk_id", p),
    documentId: str(o, "document_id", p),
    documentName: str(o, "document_name", p),
    pageStart: nullableInt(o, "page_start", p),
    pageEnd: nullableInt(o, "page_end", p),
    sectionPath: nullableStr(o, "section_path", p),
    excerpt: str(o, "excerpt", p),
  };
}

function parseTrace(raw: unknown, p: string): RetrievalTrace {
  const o = obj(raw, p);
  const timings = obj(o.timings_ms, `${p}.timings_ms`);
  return {
    mode: str(o, "mode", p),
    strategy: str(o, "strategy", p),
    topK: int(o, "top_k", p),
    candidates: int(o, "candidates", p),
    sourcesSupplied: int(o, "sources_supplied", p),
    timingsMs: Object.fromEntries(
      Object.entries(timings).filter((e): e is [string, number] => typeof e[1] === "number"),
    ),
  };
}

export function parseAnswer(raw: unknown): Answer {
  const o = obj(raw, "answer");
  return {
    conversationId: str(o, "conversation_id", "answer"),
    messageId: str(o, "message_id", "answer"),
    answer: str(o, "answer", "answer"),
    citations: arr(o, "citations", "answer", parseCitation),
    abstained: bool(o, "abstained", "answer"),
    abstainReason: nullableStr(o, "abstain_reason", "answer"),
    retrieval: parseTrace(o.retrieval, "answer.retrieval"),
    model: nullableStr(o, "model", "answer"),
    promptVersion: str(o, "prompt_version", "answer"),
    latencyMs: int(o, "latency_ms", "answer"),
    requestId: nullableStr(o, "request_id", "answer"),
  };
}

function parseSummary(o: Obj, p: string): ConversationSummary {
  return {
    id: str(o, "id", p),
    title: str(o, "title", p),
    updatedAt: str(o, "updated_at", p),
    messageCount: int(o, "message_count", p),
  };
}

function parseMessage(raw: unknown, p: string): ChatMessage {
  const o = obj(raw, p);
  const meta = obj(o.metadata, `${p}.metadata`);
  const fb = o.feedback ? obj(o.feedback, `${p}.feedback`) : null;
  return {
    id: str(o, "id", p),
    role: str(o, "role", p) === "user" ? "user" : "assistant",
    content: str(o, "content", p),
    citations: arr(o, "citations", p, parseCitation),
    abstained: meta.abstained === true,
    retrieval: meta.retrieval ? parseTrace(meta.retrieval, `${p}.retrieval`) : null,
    model: typeof meta.model === "string" ? meta.model : null,
    promptVersion: typeof meta.prompt_version === "string" ? meta.prompt_version : null,
    latencyMs: typeof meta.latency_ms === "number" ? meta.latency_ms : null,
    feedback: fb
      ? {
          rating: str(fb, "rating", p) === "helpful" ? "helpful" : "not_helpful",
          reason: nullableStr(fb, "reason", p),
        }
      : null,
    createdAt: str(o, "created_at", p),
  };
}

export function parseConversation(raw: unknown): ConversationDetail {
  const o = obj(raw, "conversation");
  return {
    ...parseSummary(o, "conversation"),
    messages: arr(o, "messages", "conversation", parseMessage),
  };
}

export async function askQuestion(
  body: {
    question: string;
    conversationId: string | null;
    documentIds: string[] | null;
    mode: RetrievalMode;
  },
  signal?: AbortSignal,
) {
  return (
    await requestJson("/api/v1/chat/query", parseAnswer, {
      method: "POST",
      json: {
        question: body.question,
        conversation_id: body.conversationId,
        document_ids: body.documentIds,
        retrieval_config: { mode: body.mode },
      },
      // CPU generation with a 4B model takes tens of seconds; loading it can take longer.
      timeoutMs: 600_000,
      signal,
    })
  ).data;
}

export async function fetchConversations(signal?: AbortSignal) {
  return (
    await requestJson(
      "/api/v1/conversations?limit=100",
      (raw) => arr(obj(raw, "page"), "items", "page", (c, p) => parseSummary(obj(c, p), p)),
      { signal },
    )
  ).data;
}

export async function fetchConversation(id: string, signal?: AbortSignal) {
  return (
    await requestJson(`/api/v1/conversations/${encodeURIComponent(id)}`, parseConversation, {
      signal,
    })
  ).data;
}

export async function renameConversation(id: string, title: string) {
  return (
    await requestJson(`/api/v1/conversations/${encodeURIComponent(id)}`, parseConversation, {
      method: "PATCH",
      json: { title },
    })
  ).data;
}

export async function deleteConversation(id: string) {
  await requestJson(`/api/v1/conversations/${encodeURIComponent(id)}`, () => undefined, {
    method: "DELETE",
  });
}

export async function sendFeedback(
  messageId: string,
  rating: "helpful" | "not_helpful",
  reason: string | null,
) {
  await requestJson(`/api/v1/messages/${encodeURIComponent(messageId)}/feedback`, () => undefined, {
    method: "PUT",
    json: { rating, reason },
  });
}

/** "page 2", "pages 2–3", heading path, or null. */
export function citationLocation(c: {
  pageStart: number | null;
  pageEnd: number | null;
  sectionPath: string | null;
}): string | null {
  const page =
    c.pageStart === null
      ? null
      : c.pageEnd !== null && c.pageEnd !== c.pageStart
        ? `pages ${c.pageStart}–${c.pageEnd}`
        : `page ${c.pageStart}`;
  return [page, c.sectionPath].filter(Boolean).join(" · ") || null;
}
