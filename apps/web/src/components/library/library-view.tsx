"use client";

import { ChevronLeft, ChevronRight, FolderOpen, Info, RotateCw, Upload } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { CopyCommand } from "@/components/ui/copy-command";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { ApiError } from "@/lib/api/client";
import {
  fetchDocuments,
  fetchUploadPolicy,
  type DocumentPage,
  type LibraryDocument,
  type UploadPolicy,
} from "@/lib/api/documents";

import { DeleteDocumentDialog } from "./delete-document-dialog";
import { DocumentsTable } from "./documents-table";
import { UploadDropzone } from "./upload-dropzone";
import { UploadQueue } from "./upload-queue";
import { useUploadQueue } from "./use-upload-queue";

export const PAGE_SIZE = 25;

type LibraryState =
  | { kind: "loading" }
  | { kind: "error"; error: ApiError }
  | { kind: "loaded"; policy: UploadPolicy; page: DocumentPage; readyCount: number };

/** The exact recovery command for errors the user can fix locally (DRD §13). */
const RECOVERY: Record<string, string> = {
  api_unreachable: "./scripts/dev.ps1 api",
  timeout: "./scripts/dev.ps1 api",
  database_unavailable: "./scripts/db.ps1 start",
  schema_not_migrated: "./scripts/dev.ps1 migrate",
  workspace_not_initialized: "./scripts/dev.ps1 migrate",
};

function asApiError(err: unknown): ApiError {
  return err instanceof ApiError
    ? err
    : new ApiError("unexpected", "The library could not be loaded.", null, null);
}

function LoadingRows() {
  return (
    <ul aria-label="Loading documents" className="divide-y">
      {Array.from({ length: 4 }, (_, i) => (
        <li key={i} className="flex items-center gap-6 px-5 py-4">
          <Skeleton className="h-4 w-56 max-w-[40%]" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="ml-auto h-4 w-28" />
        </li>
      ))}
    </ul>
  );
}

export function LibraryView() {
  const [state, setState] = useState<LibraryState>({ kind: "loading" });
  const [offset, setOffset] = useState(0);
  const [reloadKey, setReloadKey] = useState(0);
  const [toDelete, setToDelete] = useState<LibraryDocument | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    Promise.all([
      fetchUploadPolicy(ctrl.signal),
      fetchDocuments({ limit: PAGE_SIZE, offset }, ctrl.signal),
      fetchDocuments({ limit: 1, offset: 0, status: "ready" }, ctrl.signal),
    ]).then(
      ([policy, page, ready]) =>
        setState({ kind: "loaded", policy, page, readyCount: ready.total }),
      (err: unknown) => {
        if (!ctrl.signal.aborted) setState({ kind: "error", error: asApiError(err) });
      },
    );
    return () => ctrl.abort();
  }, [offset, reloadKey]);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);
  const onUploaded = useCallback(() => {
    // Newest documents are listed first, so show page one after an upload.
    setOffset(0);
    reload();
  }, [reload]);

  const policy = state.kind === "loaded" ? state.policy : null;
  const queue = useUploadQueue(policy, onUploaded);

  const onDeleted = (doc: LibraryDocument) => {
    toast.success(`Deleted “${doc.name}”.`);
    if (state.kind === "loaded" && state.page.items.length === 1 && offset > 0) {
      setOffset(Math.max(0, offset - PAGE_SIZE));
    } else {
      reload();
    }
  };

  const retryLoad = () => {
    setState({ kind: "loading" });
    reload();
  };

  const total = state.kind === "loaded" ? state.page.total : null;
  const anyQueued = state.kind === "loaded" && state.page.items.some((d) => d.status === "queued");

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[26px] leading-tight font-semibold tracking-tight">
            Knowledge Library
          </h1>
          <p className="mt-1 text-[15px] text-muted-foreground tabular-nums" aria-live="polite">
            {state.kind === "loaded"
              ? `${total} document${total === 1 ? "" : "s"} · ${state.readyCount} indexed and ready to search`
              : "Documents you add are stored and processed on this machine only."}
          </p>
        </div>
        <Button
          onClick={() => fileInput.current?.click()}
          disabled={!policy}
          title={policy ? undefined : "Available once the library has loaded"}
        >
          <Upload aria-hidden="true" />
          Upload documents
        </Button>
      </header>

      {policy && <UploadDropzone policy={policy} onFiles={queue.addFiles} inputRef={fileInput} />}

      <UploadQueue
        items={queue.items}
        onResolveDuplicate={queue.resolveDuplicate}
        onRetry={queue.retry}
        onDismiss={queue.dismiss}
        onClearFinished={queue.clearFinished}
      />

      {anyQueued && (
        // Disabled-with-reason (DRD §13): honest about what M1 does and doesn't do yet.
        <p className="flex items-start gap-2.5 rounded-xl border bg-card px-5 py-3 text-[14px]">
          <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-info" />
          <span>
            Documents are stored safely and wait in the queue. Text extraction, chunking and
            indexing arrive with the ingestion pipeline (milestone M2); until then documents stay
            Queued and can&apos;t be searched.
          </span>
        </p>
      )}

      <section aria-labelledby="documents-heading" className="rounded-xl border bg-card">
        <h2 id="documents-heading" className="sr-only">
          Documents
        </h2>

        {state.kind === "loading" && <LoadingRows />}

        {state.kind === "error" && (
          <div className="px-5 py-5" role="alert">
            <StatusBadge tone="danger">Library unavailable</StatusBadge>
            <p className="mt-2 max-w-prose text-muted-foreground">{state.error.message}</p>
            {RECOVERY[state.error.code] && <CopyCommand command={RECOVERY[state.error.code]} />}
            {state.error.requestId && (
              <p className="mt-3 font-mono text-[12px] text-muted-foreground">
                Request ID: {state.error.requestId}
              </p>
            )}
            <Button variant="outline" size="sm" className="mt-4" onClick={retryLoad}>
              <RotateCw aria-hidden="true" />
              Try again
            </Button>
          </div>
        )}

        {state.kind === "loaded" && state.page.total === 0 && (
          <div className="flex flex-col items-start gap-3 px-5 py-10 sm:items-center sm:text-center">
            <FolderOpen aria-hidden="true" className="size-6 text-muted-foreground" />
            <div>
              <p className="text-[16px] font-semibold">No documents yet</p>
              <p className="mt-1 max-w-prose text-muted-foreground">
                Add PDFs with a text layer, Word documents, plain-text or Markdown files. KnowFlow
                will index them so you can ask questions with cited answers.
              </p>
            </div>
            <Button onClick={() => fileInput.current?.click()}>
              <Upload aria-hidden="true" />
              Upload your first document
            </Button>
          </div>
        )}

        {state.kind === "loaded" && state.page.total > 0 && (
          <>
            <DocumentsTable documents={state.page.items} onDelete={setToDelete} />
            {state.page.total > PAGE_SIZE && (
              <nav
                aria-label="Document pages"
                className="flex items-center justify-between gap-3 border-t px-5 py-3"
              >
                <p className="text-[13px] text-muted-foreground tabular-nums">
                  {offset + 1}–{offset + state.page.items.length} of {state.page.total}
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={offset === 0}
                    onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                  >
                    <ChevronLeft aria-hidden="true" />
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={offset + PAGE_SIZE >= state.page.total}
                    onClick={() => setOffset(offset + PAGE_SIZE)}
                  >
                    Next
                    <ChevronRight aria-hidden="true" />
                  </Button>
                </div>
              </nav>
            )}
          </>
        )}
      </section>

      <DeleteDocumentDialog
        document={toDelete}
        onClose={() => setToDelete(null)}
        onDeleted={onDeleted}
      />
    </div>
  );
}
