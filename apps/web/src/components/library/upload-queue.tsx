"use client";

import { CopyPlus, RotateCw, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { StatusBadge, type StatusTone } from "@/components/ui/status-badge";
import { formatBytes, type DuplicateAction } from "@/lib/api/documents";

import type { UploadItem } from "./use-upload-queue";

function stateDisplay(item: UploadItem): { tone: StatusTone; label: string } {
  switch (item.state) {
    case "waiting":
      return { tone: "neutral", label: "Waiting" };
    case "uploading":
      return { tone: "pending", label: `Uploading ${Math.round(item.progress * 100)}%` };
    case "duplicate":
      return { tone: "warning", label: "Already in library" };
    case "rejected":
      return { tone: "danger", label: "Not accepted" };
    case "failed":
      return { tone: "danger", label: "Upload failed" };
    case "done":
      return { tone: "ok", label: item.outcome === "kept_existing" ? "Skipped" : "Uploaded" };
  }
}

function doneMessage(item: UploadItem): string {
  switch (item.outcome) {
    case "kept_existing":
    case "skipped":
      return "Kept the existing document. Nothing new was added.";
    case "reindexed":
      return `Queued “${item.document?.name ?? item.file.name}” for processing again.`;
    case "new_version":
      return `Added as version ${item.document?.version ?? 2} and queued for processing.`;
    default:
      return "Stored and queued for processing.";
  }
}

function DuplicateChoice({
  item,
  onResolve,
}: {
  item: UploadItem;
  onResolve: (action: DuplicateAction) => void;
}) {
  const existing = item.existing;
  if (!existing) return null;
  const uploaded = new Date(existing.createdAt).toLocaleDateString();
  return (
    <div className="mt-2 rounded-lg border bg-background p-3" role="group" aria-label="Duplicate">
      <p>
        This file has identical content to <span className="font-medium">{existing.name}</span>
        {existing.version > 1 && ` (version ${existing.version})`}, uploaded {uploaded}. What should
        KnowFlow do?
      </p>
      <div className="mt-2.5 flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={() => onResolve("skip")}>
          Keep existing
        </Button>
        <Button size="sm" variant="outline" onClick={() => onResolve("reindex")}>
          <RotateCw aria-hidden="true" />
          Re-index existing
        </Button>
        <Button size="sm" variant="outline" onClick={() => onResolve("new_version")}>
          <CopyPlus aria-hidden="true" />
          Upload as new version
        </Button>
      </div>
    </div>
  );
}

export function UploadQueue({
  items,
  onResolveDuplicate,
  onRetry,
  onDismiss,
  onClearFinished,
}: {
  items: UploadItem[];
  onResolveDuplicate: (id: string, action: DuplicateAction) => void;
  onRetry: (id: string) => void;
  onDismiss: (id: string) => void;
  onClearFinished: () => void;
}) {
  if (items.length === 0) return null;
  const finished = items.some((i) => ["done", "rejected", "failed"].includes(i.state));

  return (
    <section aria-labelledby="uploads-heading" className="rounded-xl border bg-card">
      <div className="flex items-center justify-between gap-3 border-b px-5 py-3">
        <h2 id="uploads-heading" className="font-semibold">
          Uploads
        </h2>
        {finished && (
          <Button variant="ghost" size="sm" onClick={onClearFinished}>
            Clear finished
          </Button>
        )}
      </div>
      <ul className="divide-y" aria-live="polite">
        {items.map((item) => {
          const { tone, label } = stateDisplay(item);
          return (
            <li key={item.id} className="px-5 py-3">
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                <p className="min-w-0 flex-1 truncate font-medium" title={item.file.name}>
                  {item.file.name}
                </p>
                <span className="text-[12px] text-muted-foreground tabular-nums">
                  {formatBytes(item.file.size)}
                </span>
                <StatusBadge tone={tone}>{label}</StatusBadge>
                {item.state === "failed" && (
                  <Button size="sm" variant="outline" onClick={() => onRetry(item.id)}>
                    <RotateCw aria-hidden="true" />
                    Retry
                  </Button>
                )}
                {["done", "rejected", "failed"].includes(item.state) && (
                  <Button
                    size="icon-sm"
                    variant="ghost"
                    onClick={() => onDismiss(item.id)}
                    aria-label={`Dismiss ${item.file.name}`}
                  >
                    <X aria-hidden="true" />
                  </Button>
                )}
              </div>
              {item.state === "uploading" && (
                <div
                  role="progressbar"
                  aria-label={`Uploading ${item.file.name}`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.round(item.progress * 100)}
                  className="mt-2 h-1 overflow-hidden rounded-full bg-muted"
                >
                  <div
                    className="h-full bg-primary transition-[width] duration-150"
                    style={{ width: `${Math.round(item.progress * 100)}%` }}
                  />
                </div>
              )}
              {(item.state === "rejected" || item.state === "failed") && (
                <p className="mt-1 text-muted-foreground">
                  {item.message}
                  {item.requestId && (
                    <span className="ml-2 font-mono text-[12px]">Request ID: {item.requestId}</span>
                  )}
                </p>
              )}
              {item.state === "done" && (
                <p className="mt-1 text-muted-foreground">{doneMessage(item)}</p>
              )}
              {item.state === "duplicate" && (
                <DuplicateChoice
                  item={item}
                  onResolve={(action) => onResolveDuplicate(item.id, action)}
                />
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
