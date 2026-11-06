"use client";

import { RotateCw } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { ApiError } from "@/lib/api/client";
import {
  fetchChunks,
  fetchExtraction,
  formatBytes,
  type ChunkPage,
  type ChunkStrategy,
  type ExtractionPreview,
  type LibraryDocument,
} from "@/lib/api/documents";

import { DocumentStatusBadge } from "./document-status";

const CHUNK_PAGE = 10;

const GRANULARITY: Record<string, string> = {
  page: "Citations point to pages.",
  section: "This format has no pages, so citations point to headings.",
  document: "No pages or headings were found, so citations point to the whole document.",
};

export function locationLabel(c: {
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

type Loaded<T> = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ok"; data: T };

function message(err: unknown) {
  return err instanceof ApiError ? err.message : "Could not load this part of the document.";
}

function Meta({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-1.5">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right tabular-nums">{children}</dd>
    </div>
  );
}

/** DRD §7.2 document detail drawer: metadata, extraction preview and chunk sample. */
export function DocumentDrawer({
  document: doc,
  onClose,
  onRetry,
}: {
  document: LibraryDocument | null;
  onClose: () => void;
  onRetry: (doc: LibraryDocument) => void;
}) {
  const [strategy, setStrategy] = useState<ChunkStrategy>("recursive");
  const [offset, setOffset] = useState(0);
  const [chunks, setChunks] = useState<Loaded<ChunkPage>>({ kind: "loading" });
  const [extraction, setExtraction] = useState<Loaded<ExtractionPreview>>({ kind: "loading" });
  const ready = doc?.status === "ready";
  const docId = doc?.id;

  useEffect(() => {
    if (!docId || !ready) return;
    const ctrl = new AbortController();
    fetchExtraction(docId, ctrl.signal).then(
      (data) => setExtraction({ kind: "ok", data }),
      (err: unknown) =>
        !ctrl.signal.aborted && setExtraction({ kind: "error", message: message(err) }),
    );
    return () => ctrl.abort();
  }, [docId, ready]);

  useEffect(() => {
    if (!docId || !ready) return;
    const ctrl = new AbortController();
    fetchChunks(docId, { strategy, limit: CHUNK_PAGE, offset }, ctrl.signal).then(
      (data) => setChunks({ kind: "ok", data }),
      (err: unknown) => !ctrl.signal.aborted && setChunks({ kind: "error", message: message(err) }),
    );
    return () => ctrl.abort();
  }, [docId, ready, strategy, offset]);

  const close = (open: boolean) => {
    if (open) return;
    setStrategy("recursive");
    setOffset(0);
    setChunks({ kind: "loading" });
    setExtraction({ kind: "loading" });
    onClose();
  };

  const pickStrategy = (s: ChunkStrategy) => {
    setStrategy(s);
    setOffset(0);
    setChunks({ kind: "loading" });
  };

  return (
    <Sheet open={doc !== null} onOpenChange={close}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        {doc && (
          <>
            <SheetHeader className="border-b px-6 py-5">
              <SheetTitle className="pr-8 text-[18px] font-semibold break-words">
                {doc.name}
              </SheetTitle>
              <SheetDescription asChild>
                <div className="mt-1 flex items-center gap-3">
                  <DocumentStatusBadge status={doc.status} />
                  <span className="tabular-nums">{formatBytes(doc.sizeBytes)}</span>
                </div>
              </SheetDescription>
            </SheetHeader>

            <div className="flex flex-col gap-6 px-6 pb-8">
              {doc.lastError && (
                <div role="alert" className="rounded-lg border p-4">
                  <StatusBadge tone="danger">Processing failed</StatusBadge>
                  <p className="mt-2">{doc.lastError.message}</p>
                  <p className="mt-1 font-mono text-[12px] text-muted-foreground">
                    {doc.lastError.code}
                  </p>
                  <Button size="sm" className="mt-3" onClick={() => onRetry(doc)}>
                    <RotateCw aria-hidden="true" />
                    Retry processing
                  </Button>
                </div>
              )}

              <section aria-labelledby="doc-meta">
                <h3 id="doc-meta" className="text-[15px] font-semibold">
                  Details
                </h3>
                <dl className="mt-2 divide-y text-[14px]">
                  <Meta label="Pages">{doc.pageCount ?? "—"}</Meta>
                  <Meta label="Chunks (recursive)">{doc.chunkCount ?? "—"}</Meta>
                  <Meta label="Extracted characters">
                    {doc.extractedCharCount?.toLocaleString() ?? "—"}
                  </Meta>
                  <Meta label="Version">{doc.version}</Meta>
                  <Meta label="Attempts">{doc.latestJob?.attempts ?? 0}</Meta>
                  <Meta label="SHA-256">
                    <span className="font-mono text-[12px] break-all">{doc.sha256}</span>
                  </Meta>
                </dl>
                {doc.citationGranularity && (
                  <p className="mt-2 text-[13px] text-muted-foreground">
                    {GRANULARITY[doc.citationGranularity]}
                  </p>
                )}
              </section>

              {!ready && !doc.lastError && (
                <p className="text-muted-foreground">
                  The extraction preview and chunks appear here once processing finishes.
                </p>
              )}

              {ready && (
                <section aria-labelledby="doc-preview">
                  <h3 id="doc-preview" className="text-[15px] font-semibold">
                    Extraction preview
                  </h3>
                  {extraction.kind === "loading" && <Skeleton className="mt-2 h-24 w-full" />}
                  {extraction.kind === "error" && (
                    <p className="mt-2 text-muted-foreground">{extraction.message}</p>
                  )}
                  {extraction.kind === "ok" && (
                    <div className="mt-2 flex flex-col gap-3">
                      {extraction.data.sections.map((s) => (
                        <figure key={s.ordinal} className="rounded-lg border bg-background p-3">
                          <figcaption className="text-[12px] text-muted-foreground">
                            {locationLabel({
                              pageStart: s.pageNumber,
                              pageEnd: s.pageNumber,
                              sectionPath: s.sectionPath,
                            }) ?? "Whole document"}
                          </figcaption>
                          <p className="mt-1 text-[13px] whitespace-pre-wrap">{s.text}</p>
                        </figure>
                      ))}
                      <p className="text-[12px] text-muted-foreground tabular-nums">
                        Showing {extraction.data.sections.length} of {extraction.data.totalSections}{" "}
                        extracted {doc.citationGranularity === "page" ? "pages" : "sections"}.
                      </p>
                    </div>
                  )}
                </section>
              )}

              {ready && (
                <section aria-labelledby="doc-chunks">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 id="doc-chunks" className="text-[15px] font-semibold">
                      Chunks
                    </h3>
                    <div role="group" aria-label="Chunking strategy" className="flex gap-1">
                      {(["recursive", "fixed"] as const).map((s) => (
                        <Button
                          key={s}
                          size="sm"
                          variant={strategy === s ? "secondary" : "ghost"}
                          aria-pressed={strategy === s}
                          onClick={() => pickStrategy(s)}
                        >
                          {s === "recursive" ? "Recursive" : "Fixed-size"}
                        </Button>
                      ))}
                    </div>
                  </div>
                  {chunks.kind === "loading" && <Skeleton className="mt-2 h-32 w-full" />}
                  {chunks.kind === "error" && (
                    <p className="mt-2 text-muted-foreground">{chunks.message}</p>
                  )}
                  {chunks.kind === "ok" && (
                    <>
                      <ol className="mt-2 flex flex-col gap-2">
                        {chunks.data.items.map((c) => (
                          <li key={c.id} className="rounded-lg border bg-background p-3">
                            <p className="flex justify-between gap-3 text-[12px] text-muted-foreground">
                              <span>
                                #{c.index + 1}
                                {locationLabel(c) && ` · ${locationLabel(c)}`}
                              </span>
                              <span className="tabular-nums">≈{c.tokenCount} tokens</span>
                            </p>
                            <p className="mt-1 line-clamp-6 text-[13px] whitespace-pre-wrap">
                              {c.text}
                            </p>
                          </li>
                        ))}
                      </ol>
                      <div className="mt-3 flex items-center justify-between">
                        <p className="text-[12px] text-muted-foreground tabular-nums">
                          {chunks.data.total === 0
                            ? "No chunks"
                            : `${offset + 1}–${offset + chunks.data.items.length} of ${chunks.data.total}`}
                        </p>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={offset === 0}
                            onClick={() => {
                              setChunks({ kind: "loading" });
                              setOffset(Math.max(0, offset - CHUNK_PAGE));
                            }}
                          >
                            Previous
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={offset + CHUNK_PAGE >= chunks.data.total}
                            onClick={() => {
                              setChunks({ kind: "loading" });
                              setOffset(offset + CHUNK_PAGE);
                            }}
                          >
                            Next
                          </Button>
                        </div>
                      </div>
                    </>
                  )}
                </section>
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
