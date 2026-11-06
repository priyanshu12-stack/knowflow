"use client";

import {
  ChevronDown,
  FileText,
  Loader2,
  MessageSquarePlus,
  Pencil,
  RotateCw,
  SendHorizontal,
  ThumbsDown,
  ThumbsUp,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { CopyCommand } from "@/components/ui/copy-command";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { useSystemStatus } from "@/components/system-status/system-status-provider";
import {
  askQuestion,
  citationLocation,
  deleteConversation,
  fetchConversation,
  fetchConversations,
  renameConversation,
  sendFeedback,
  type ChatMessage,
  type Citation,
  type ConversationSummary,
  type RetrievalMode,
  type RetrievalTrace,
} from "@/lib/api/chat";
import { ApiError } from "@/lib/api/client";
import { fetchDocuments, type LibraryDocument } from "@/lib/api/documents";

import { AnswerText, CitationChip } from "./answer-text";
import { SourceDrawer } from "./source-drawer";

function asApiError(err: unknown) {
  return err instanceof ApiError
    ? err
    : new ApiError("unexpected", "Something went wrong.", null, null);
}

const MODE_LABEL: Record<RetrievalMode, string> = {
  dense: "Semantic search",
  lexical: "Keyword search",
  hybrid: "Hybrid search",
};

const TIMING_LABEL: Record<string, string> = {
  embed_query: "Embed question",
  dense: "Vector search",
  lexical: "Keyword search",
  fusion: "Rank fusion (RRF)",
  rerank: "Rerank",
  generation: "Generate answer",
};

const STAGES = ["embed_query", "dense", "lexical", "fusion", "rerank", "generation"];
const stageOrder = (k: string) => (STAGES.includes(k) ? STAGES.indexOf(k) : STAGES.length);

function seconds(ms: number) {
  return `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0)} s`;
}

function TraceDetails({
  trace,
  model,
  promptVersion,
}: {
  trace: RetrievalTrace;
  model: string | null;
  promptVersion: string | null;
}) {
  return (
    <div className="mt-3 rounded-lg border bg-background p-3 text-[13px]">
      <p className="font-medium">How this was found</p>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-6 gap-y-1">
        <dt className="text-muted-foreground">Retrieval</dt>
        <dd>
          {MODE_LABEL[trace.mode as RetrievalMode] ?? trace.mode} over {trace.strategy} chunks
        </dd>
        <dt className="text-muted-foreground">Passages</dt>
        <dd className="tabular-nums">
          {trace.candidates} retrieved (top {trace.topK}), {trace.sourcesSupplied} given to the
          model
        </dd>
        {model && (
          <>
            <dt className="text-muted-foreground">Model</dt>
            <dd className="font-mono text-[12px]">{model}</dd>
          </>
        )}
        {promptVersion && (
          <>
            <dt className="text-muted-foreground">Prompt</dt>
            <dd className="font-mono text-[12px]">{promptVersion}</dd>
          </>
        )}
        {Object.entries(trace.timingsMs)
          // Stored as JSONB, which doesn't keep key order: show stages in pipeline order.
          .sort(([a], [b]) => stageOrder(a) - stageOrder(b))
          .map(([k, v]) => (
            <TimingRow key={k} label={TIMING_LABEL[k] ?? k} value={seconds(v)} />
          ))}
      </dl>
    </div>
  );
}

function TimingRow({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-mono text-[12px] tabular-nums">{value}</dd>
    </>
  );
}

function Feedback({ message, onSaved }: { message: ChatMessage; onSaved: () => void }) {
  const [askingReason, setAskingReason] = useState(false);
  const [reason, setReason] = useState("");
  const current = message.feedback?.rating ?? null;

  const save = async (rating: "helpful" | "not_helpful", why: string | null) => {
    try {
      await sendFeedback(message.id, rating, why);
      toast.success("Thanks, your feedback was saved.");
      setAskingReason(false);
      onSaved();
    } catch (err) {
      toast.error(asApiError(err).message);
    }
  };

  return (
    <div className="mt-3">
      <div className="flex items-center gap-1" role="group" aria-label="Was this answer helpful?">
        <span className="mr-1 text-[12px] text-muted-foreground">Helpful?</span>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Helpful"
          aria-pressed={current === "helpful"}
          className="aria-pressed:text-primary"
          onClick={() => void save("helpful", null)}
        >
          <ThumbsUp aria-hidden="true" />
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Not helpful"
          aria-pressed={current === "not_helpful"}
          className="aria-pressed:text-danger"
          onClick={() => setAskingReason(true)}
        >
          <ThumbsDown aria-hidden="true" />
        </Button>
      </div>
      {askingReason && (
        <form
          className="mt-2 flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void save("not_helpful", reason.trim() || null);
          }}
        >
          <div className="flex min-w-[220px] flex-1 flex-col gap-1">
            <Label htmlFor={`reason-${message.id}`} className="text-[12px]">
              What was wrong? (optional)
            </Label>
            <Input
              id={`reason-${message.id}`}
              value={reason}
              maxLength={1000}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. cited the wrong page"
            />
          </div>
          <Button size="sm" type="submit">
            Send feedback
          </Button>
          <Button size="sm" variant="ghost" type="button" onClick={() => setAskingReason(false)}>
            Cancel
          </Button>
        </form>
      )}
    </div>
  );
}

function AssistantMessage({
  message,
  showDetails,
  selected,
  onCite,
  onFeedback,
}: {
  message: ChatMessage;
  showDetails: boolean;
  selected: string | null;
  onCite: (c: Citation, messageId: string) => void;
  onFeedback: () => void;
}) {
  const selectedNumber = selected?.startsWith(`${message.id}:`)
    ? Number(selected.split(":")[1])
    : null;
  return (
    <article className="rounded-xl border bg-card px-5 py-4" aria-label="Answer">
      {message.abstained ? (
        <>
          <StatusBadge tone="warning">No supporting source found</StatusBadge>
          <p className="mt-2 text-[15px] leading-[1.6]">
            {message.content.replace(/^No supporting source found\.\s*/, "")}
          </p>
        </>
      ) : (
        <AnswerText
          text={message.content}
          citations={message.citations}
          selected={selectedNumber}
          onSelect={(c) => onCite(c, message.id)}
        />
      )}

      {message.citations.length > 0 && (
        <section className="mt-4 border-t pt-3" aria-label="Sources used">
          <p className="text-[12px] font-medium tracking-wide text-muted-foreground uppercase">
            Sources used
          </p>
          <ul className="mt-2 flex flex-col gap-1.5">
            {message.citations.map((c) => (
              <li key={c.number} className="flex items-center gap-2 text-[14px]">
                <CitationChip
                  citation={c}
                  selected={selectedNumber === c.number}
                  onSelect={(x) => onCite(x, message.id)}
                />
                <FileText aria-hidden="true" className="size-3.5 text-muted-foreground" />
                <span className="truncate font-medium">{c.documentName}</span>
                {citationLocation(c) && (
                  <span className="truncate text-muted-foreground">· {citationLocation(c)}</span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {message.retrieval && (
        <p className="mt-3 text-[12px] text-muted-foreground tabular-nums">
          {/* DRD §7.3: evidence quality as counts, never a confidence percentage. */}
          Searched {message.retrieval.candidates} passages, used {message.retrieval.sourcesSupplied}
          {message.latencyMs !== null && ` · ${seconds(message.latencyMs)}`}
          {message.model && ` · ${message.model}`}
        </p>
      )}
      {showDetails && message.retrieval && (
        <TraceDetails
          trace={message.retrieval}
          model={message.model}
          promptVersion={message.promptVersion}
        />
      )}
      <Feedback message={message} onSaved={onFeedback} />
    </article>
  );
}

function ConversationList({
  conversations,
  activeId,
  onSelect,
  onNew,
  onRename,
  onDelete,
}: {
  conversations: ConversationSummary[] | null;
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (c: ConversationSummary) => void;
  onDelete: (c: ConversationSummary) => void;
}) {
  return (
    <nav aria-label="Conversations" className="flex flex-col gap-2">
      <Button variant="outline" onClick={onNew} className="justify-start">
        <MessageSquarePlus aria-hidden="true" />
        New conversation
      </Button>
      {conversations === null && <Skeleton className="h-20 w-full" />}
      {conversations?.length === 0 && (
        <p className="px-1 text-[13px] text-muted-foreground">
          Your questions and answers are saved here.
        </p>
      )}
      <ul className="flex flex-col gap-0.5">
        {conversations?.map((c) => (
          <li key={c.id} className="group flex items-center gap-1">
            <button
              type="button"
              onClick={() => onSelect(c.id)}
              aria-current={c.id === activeId ? "page" : undefined}
              className="min-w-0 flex-1 truncate rounded-lg px-2.5 py-1.5 text-left text-[14px] hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none aria-[current=page]:bg-accent aria-[current=page]:font-medium aria-[current=page]:text-primary"
              title={c.title}
            >
              {c.title}
            </button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon-xs" aria-label={`Options for ${c.title}`}>
                  <ChevronDown aria-hidden="true" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={() => onRename(c)}>
                  <Pencil aria-hidden="true" />
                  Rename…
                </DropdownMenuItem>
                <DropdownMenuItem variant="destructive" onSelect={() => onDelete(c)}>
                  <Trash2 aria-hidden="true" />
                  Delete…
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </li>
        ))}
      </ul>
    </nav>
  );
}

type Pending = { question: string; startedAt: number } | null;

/** DRD §7.3 Ask KnowFlow: a focused research workspace, not a consumer chat clone. */
export function AskView() {
  const { status: system } = useSystemStatus();
  const [readyDocs, setReadyDocs] = useState<LibraryDocument[] | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[] | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loadingConversation, setLoadingConversation] = useState(false);
  const [question, setQuestion] = useState("");
  const [scope, setScope] = useState<string[]>([]);
  const [mode, setMode] = useState<RetrievalMode>("dense");
  const [showDetails, setShowDetails] = useState(false);
  const [pending, setPending] = useState<Pending>(null);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<{ error: ApiError; question: string } | null>(null);
  const [drawer, setDrawer] = useState<{ citation: Citation; key: string } | null>(null);
  const [renaming, setRenaming] = useState<ConversationSummary | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const [deleting, setDeleting] = useState<ConversationSummary | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const loadConversations = useCallback(() => {
    fetchConversations().then(setConversations, () => setConversations([]));
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchDocuments({ limit: 100, offset: 0, status: "ready" }, ctrl.signal).then(
      (p) => setReadyDocs(p.items),
      () => !ctrl.signal.aborted && setReadyDocs([]),
    );
    fetchConversations(ctrl.signal).then(setConversations, () => {
      if (!ctrl.signal.aborted) setConversations([]);
    });
    return () => ctrl.abort();
  }, []);

  const loadConversation = useCallback((id: string) => {
    setLoadingConversation(true);
    setError(null);
    fetchConversation(id)
      .then((c) => {
        setActiveId(c.id);
        setMessages(c.messages);
      })
      .catch((err: unknown) => toast.error(asApiError(err).message))
      .finally(() => setLoadingConversation(false));
  }, []);

  useEffect(() => {
    if (!pending) return;
    const id = window.setInterval(() => setElapsed(Date.now() - pending.startedAt), 500);
    return () => window.clearInterval(id);
  }, [pending]);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "end", behavior: "smooth" });
  }, [messages.length, pending]);

  const submit = async (text: string) => {
    const q = text.trim();
    if (!q || pending) return;
    setError(null);
    setPending({ question: q, startedAt: Date.now() });
    setElapsed(0);
    setQuestion("");
    try {
      const answer = await askQuestion({
        question: q,
        conversationId: activeId,
        documentIds: scope.length ? scope : null,
        mode,
      });
      const c = await fetchConversation(answer.conversationId);
      setActiveId(c.id);
      setMessages(c.messages);
      loadConversations();
    } catch (err) {
      setError({ error: asApiError(err), question: q });
      setQuestion(q);
    } finally {
      setPending(null);
      inputRef.current?.focus();
    }
  };

  const newConversation = () => {
    setActiveId(null);
    setMessages([]);
    setError(null);
    inputRef.current?.focus();
  };

  const generation =
    system.kind === "loaded"
      ? system.data.checks.find((c) => c.name === "generation_model")
      : undefined;
  const modelMissing = generation !== undefined && generation.state !== "ok";
  const noDocs = readyDocs !== null && readyDocs.length === 0;
  const scopeLabel =
    scope.length === 0
      ? `All ready documents${readyDocs ? ` (${readyDocs.length})` : ""}`
      : `${scope.length} selected document${scope.length === 1 ? "" : "s"}`;

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-[26px] leading-tight font-semibold tracking-tight">Ask KnowFlow</h1>
        <p className="mt-1 max-w-prose text-[15px] text-muted-foreground">
          Answers come only from passages retrieved from your documents, with numbered citations you
          can open. KnowFlow searches a limited set of passages; it doesn&apos;t read every
          document.
        </p>
      </header>

      {modelMissing && generation?.remediation && (
        <div role="status" className="rounded-xl border bg-card px-5 py-4">
          <StatusBadge tone="warning">Generation model not installed</StatusBadge>
          <p className="mt-2 text-[14px]">{generation.detail} Answers need it:</p>
          <CopyCommand command={generation.remediation} />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[240px_minmax(0,1fr)]">
        <aside className="lg:sticky lg:top-20 lg:self-start">
          <details className="group lg:hidden" open={false}>
            <summary className="cursor-pointer rounded-lg border bg-card px-3 py-2 text-[14px] font-medium">
              Conversations{conversations ? ` (${conversations.length})` : ""}
            </summary>
            <div className="mt-2">
              <ConversationList
                conversations={conversations}
                activeId={activeId}
                onSelect={loadConversation}
                onNew={newConversation}
                onRename={(c) => {
                  setRenaming(c);
                  setNewTitle(c.title);
                }}
                onDelete={setDeleting}
              />
            </div>
          </details>
          <div className="hidden lg:block">
            <ConversationList
              conversations={conversations}
              activeId={activeId}
              onSelect={loadConversation}
              onNew={newConversation}
              onRename={(c) => {
                setRenaming(c);
                setNewTitle(c.title);
              }}
              onDelete={setDeleting}
            />
          </div>
        </aside>

        <div className="flex max-w-[860px] min-w-0 flex-col gap-4">
          <div className="flex flex-wrap items-center gap-2" aria-label="Question settings">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" disabled={!readyDocs || noDocs}>
                  <FileText aria-hidden="true" />
                  {scopeLabel}
                  <ChevronDown aria-hidden="true" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="max-h-80 w-72 overflow-y-auto">
                <DropdownMenuLabel>Search in</DropdownMenuLabel>
                <DropdownMenuCheckboxItem
                  checked={scope.length === 0}
                  onCheckedChange={() => setScope([])}
                  onSelect={(e) => e.preventDefault()}
                >
                  All ready documents
                </DropdownMenuCheckboxItem>
                <DropdownMenuSeparator />
                {readyDocs?.map((d) => (
                  <DropdownMenuCheckboxItem
                    key={d.id}
                    checked={scope.includes(d.id)}
                    onSelect={(e) => e.preventDefault()}
                    onCheckedChange={(on) =>
                      setScope((s) => (on ? [...s, d.id] : s.filter((x) => x !== d.id)))
                    }
                  >
                    <span className="truncate">{d.name}</span>
                  </DropdownMenuCheckboxItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
            <label className="flex items-center gap-2 text-[13px]">
              <span className="sr-only">Retrieval profile</span>
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value as RetrievalMode)}
                className="h-8 rounded-lg border bg-background px-2 text-[13px] focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              >
                <option value="dense">Semantic search</option>
                <option value="lexical">Keyword search</option>
                <option value="hybrid">Hybrid (semantic + keyword)</option>
              </select>
            </label>
            <label className="ml-auto flex items-center gap-2 text-[13px]">
              <input
                type="checkbox"
                className="size-4 accent-primary"
                checked={showDetails}
                onChange={(e) => setShowDetails(e.target.checked)}
              />
              Show retrieval details
            </label>
          </div>

          <div className="flex flex-col gap-4" aria-live="polite">
            {noDocs && messages.length === 0 && (
              <div className="rounded-xl border bg-card px-5 py-8 text-center">
                <p className="text-[16px] font-semibold">No indexed documents yet</p>
                <p className="mt-1 text-muted-foreground">
                  Upload documents and wait until they&apos;re Ready, then ask about them here.
                </p>
                <Button asChild className="mt-4">
                  <Link href="/library">Go to Knowledge Library</Link>
                </Button>
              </div>
            )}
            {!noDocs && messages.length === 0 && !pending && !loadingConversation && (
              <div className="rounded-xl border border-dashed px-5 py-8 text-center text-muted-foreground">
                Ask a question about your{" "}
                {readyDocs
                  ? `${readyDocs.length} indexed document${readyDocs.length === 1 ? "" : "s"}`
                  : "documents"}
                . Each answer shows which passages it came from.
              </div>
            )}
            {loadingConversation && <Skeleton className="h-32 w-full" />}

            {messages.map((m) =>
              m.role === "user" ? (
                <p
                  key={m.id}
                  className="self-end rounded-xl bg-accent px-4 py-2.5 text-[15px] whitespace-pre-wrap"
                >
                  {m.content}
                </p>
              ) : (
                <AssistantMessage
                  key={m.id}
                  message={m}
                  showDetails={showDetails}
                  selected={drawer?.key ?? null}
                  onCite={(c, mid) => setDrawer({ citation: c, key: `${mid}:${c.number}` })}
                  onFeedback={() => activeId && loadConversation(activeId)}
                />
              ),
            )}

            {pending && (
              <>
                <p className="self-end rounded-xl bg-accent px-4 py-2.5 text-[15px] whitespace-pre-wrap">
                  {pending.question}
                </p>
                <div role="status" className="rounded-xl border bg-card px-5 py-4">
                  <p className="flex items-center gap-2 text-[15px]">
                    <Loader2 aria-hidden="true" className="size-4 animate-spin text-primary" />
                    Searching your documents and writing an answer…
                  </p>
                  <p className="mt-1 text-[13px] text-muted-foreground tabular-nums">
                    {Math.floor(elapsed / 1000)} s elapsed. Answers are generated on this
                    machine&apos;s CPU and usually take 30–90 seconds.
                  </p>
                </div>
              </>
            )}

            {error && (
              <div role="alert" className="rounded-xl border bg-card px-5 py-4">
                <StatusBadge tone="danger">The answer failed</StatusBadge>
                <p className="mt-2">{error.error.message}</p>
                {error.error.requestId && (
                  <p className="mt-1 font-mono text-[12px] text-muted-foreground">
                    Request ID: {error.error.requestId}
                  </p>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  className="mt-3"
                  onClick={() => void submit(error.question)}
                >
                  <RotateCw aria-hidden="true" />
                  Try again
                </Button>
              </div>
            )}
            <div ref={endRef} />
          </div>

          <form
            className="sticky bottom-4 rounded-xl border bg-card p-3 shadow-sm"
            onSubmit={(e) => {
              e.preventDefault();
              void submit(question);
            }}
          >
            <Label htmlFor="question" className="text-[13px]">
              Your question
            </Label>
            <textarea
              id="question"
              ref={inputRef}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                  e.preventDefault();
                  void submit(question);
                }
              }}
              rows={3}
              maxLength={2000}
              disabled={noDocs}
              placeholder="e.g. What is the hotel limit per night?"
              className="mt-1.5 w-full resize-y rounded-lg border bg-background px-3 py-2 text-[15px] focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:opacity-60"
            />
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              <p className="text-[12px] text-muted-foreground">
                {scopeLabel} · {MODE_LABEL[mode]} · Ctrl+Enter to send
              </p>
              <Button
                type="submit"
                disabled={!question.trim() || pending !== null || noDocs}
                title={noDocs ? "Index a document first" : undefined}
              >
                {pending ? (
                  <Loader2 aria-hidden="true" className="animate-spin" />
                ) : (
                  <SendHorizontal aria-hidden="true" />
                )}
                Ask
              </Button>
            </div>
          </form>
        </div>
      </div>

      <SourceDrawer citation={drawer?.citation ?? null} onClose={() => setDrawer(null)} />

      <AlertDialog open={renaming !== null} onOpenChange={(o) => !o && setRenaming(null)}>
        <AlertDialogContent>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!renaming || !newTitle.trim()) return;
              renameConversation(renaming.id, newTitle.trim())
                .then(() => {
                  loadConversations();
                  setRenaming(null);
                })
                .catch((err: unknown) => toast.error(asApiError(err).message));
            }}
          >
            <AlertDialogHeader>
              <AlertDialogTitle>Rename conversation</AlertDialogTitle>
              <AlertDialogDescription>
                Give this conversation a clearer title.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="my-4 flex flex-col gap-1.5">
              <Label htmlFor="conversation-title">Title</Label>
              <Input
                id="conversation-title"
                value={newTitle}
                maxLength={120}
                onChange={(e) => setNewTitle(e.target.value)}
              />
            </div>
            <AlertDialogFooter>
              <AlertDialogCancel type="button">Cancel</AlertDialogCancel>
              <Button type="submit" disabled={!newTitle.trim()}>
                Save
              </Button>
            </AlertDialogFooter>
          </form>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={deleting !== null} onOpenChange={(o) => !o && setDeleting(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this conversation?</AlertDialogTitle>
            <AlertDialogDescription>
              “{deleting?.title}” and all its questions, answers and feedback will be permanently
              deleted. Your documents are not affected.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                if (!deleting) return;
                const id = deleting.id;
                deleteConversation(id)
                  .then(() => {
                    if (id === activeId) newConversation();
                    loadConversations();
                    toast.success("Conversation deleted.");
                  })
                  .catch((err: unknown) => toast.error(asApiError(err).message));
              }}
            >
              Delete conversation
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
