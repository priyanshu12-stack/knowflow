"use client";

import { useCallback, useRef, useState } from "react";

import { ApiError } from "@/lib/api/client";
import {
  duplicateOf,
  precheckFile,
  uploadDocument,
  type DuplicateAction,
  type LibraryDocument,
  type UploadPolicy,
  type UploadResult,
} from "@/lib/api/documents";

export type UploadState = "waiting" | "uploading" | "duplicate" | "done" | "rejected" | "failed";

export interface UploadItem {
  id: string;
  file: File;
  state: UploadState;
  progress: number;
  onDuplicate?: DuplicateAction;
  /** Plain-language reason for rejected / failed items. */
  message?: string;
  requestId?: string | null;
  /** The document that already has this content (state "duplicate"). */
  existing?: LibraryDocument;
  outcome?: UploadResult["outcome"] | "kept_existing";
  document?: LibraryDocument;
}

let counter = 0;
const nextId = () => `upload-${Date.now()}-${(counter += 1)}`;

/**
 * Sequential upload queue. One file at a time keeps memory and disk pressure low on small
 * machines and makes duplicate decisions unambiguous. The ref is the source of truth so the
 * async pump never reads stale state; `items` mirrors it for rendering.
 */
export function useUploadQueue(
  policy: UploadPolicy | null,
  onUploaded: (result: UploadResult) => void,
) {
  const itemsRef = useRef<UploadItem[]>([]);
  const [items, setItems] = useState<UploadItem[]>([]);
  const running = useRef(false);

  const commit = useCallback((next: UploadItem[]) => {
    itemsRef.current = next;
    setItems(next);
  }, []);

  const patch = useCallback(
    (id: string, changes: Partial<UploadItem>) =>
      commit(itemsRef.current.map((i) => (i.id === id ? { ...i, ...changes } : i))),
    [commit],
  );

  const uploadOne = useCallback(
    async (item: UploadItem) => {
      patch(item.id, { state: "uploading", progress: 0, message: undefined });
      try {
        const result = await uploadDocument(item.file, {
          onDuplicate: item.onDuplicate,
          onProgress: (progress) => patch(item.id, { progress }),
        });
        patch(item.id, {
          state: "done",
          progress: 1,
          outcome: result.outcome,
          document: result.document,
        });
        onUploaded(result);
      } catch (err) {
        const error =
          err instanceof ApiError
            ? err
            : new ApiError("upload_failed", "The upload did not complete.", null, null);
        const existing = duplicateOf(error);
        if (existing) {
          patch(item.id, { state: "duplicate", existing, progress: 0 });
        } else {
          patch(item.id, {
            state: "failed",
            message: error.message,
            requestId: error.requestId,
          });
        }
      }
    },
    [onUploaded, patch],
  );

  const pump = useCallback(async () => {
    if (running.current) return;
    running.current = true;
    try {
      for (;;) {
        const next = itemsRef.current.find((i) => i.state === "waiting");
        if (!next) break;
        await uploadOne(next);
      }
    } finally {
      running.current = false;
    }
  }, [uploadOne]);

  const addFiles = useCallback(
    (files: File[]) => {
      if (!policy) return;
      const added = files.map((file): UploadItem => {
        const problem = precheckFile(file, policy);
        return problem
          ? { id: nextId(), file, state: "rejected", progress: 0, message: problem }
          : { id: nextId(), file, state: "waiting", progress: 0 };
      });
      commit([...itemsRef.current, ...added]);
      void pump();
    },
    [commit, policy, pump],
  );

  const resolveDuplicate = useCallback(
    (id: string, action: DuplicateAction) => {
      if (action === "skip") {
        // Nothing to send: keeping the existing document needs no second upload.
        const item = itemsRef.current.find((i) => i.id === id);
        patch(id, { state: "done", outcome: "kept_existing", document: item?.existing });
        return;
      }
      patch(id, { state: "waiting", onDuplicate: action });
      void pump();
    },
    [patch, pump],
  );

  const retry = useCallback(
    (id: string) => {
      patch(id, { state: "waiting", requestId: undefined });
      void pump();
    },
    [patch, pump],
  );

  const dismiss = useCallback(
    (id: string) => commit(itemsRef.current.filter((i) => i.id !== id)),
    [commit],
  );

  const clearFinished = useCallback(
    () => commit(itemsRef.current.filter((i) => !["done", "rejected", "failed"].includes(i.state))),
    [commit],
  );

  return { items, addFiles, resolveDuplicate, retry, dismiss, clearFinished };
}
