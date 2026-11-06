"use client";

import { useState } from "react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { deleteDocument, type LibraryDocument } from "@/lib/api/documents";

/** DRD §9: destructive actions require confirmation and explain what is deleted. */
export function DeleteDocumentDialog({
  document,
  onClose,
  onDeleted,
}: {
  document: LibraryDocument | null;
  onClose: () => void;
  onDeleted: (doc: LibraryDocument) => void;
}) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const close = () => {
    if (deleting) return;
    setError(null);
    onClose();
  };

  const confirm = async () => {
    if (!document) return;
    setDeleting(true);
    setError(null);
    try {
      await deleteDocument(document.id);
      onDeleted(document);
      onClose();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err
          : new ApiError("delete_failed", "The document could not be deleted.", null, null),
      );
    } finally {
      setDeleting(false);
    }
  };

  return (
    <AlertDialog open={document !== null} onOpenChange={(open) => !open && close()}>
      <AlertDialogContent className="sm:max-w-md">
        <AlertDialogHeader>
          <AlertDialogTitle>Delete “{document?.name}”?</AlertDialogTitle>
          <AlertDialogDescription>
            This permanently removes the stored file, its metadata and its processing history from
            this workspace, along with any indexed chunks. This can&apos;t be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        {error && (
          <p role="alert" className="text-[13px]">
            {error.message}
            {error.requestId && (
              <span className="mt-1 block font-mono text-[12px] text-muted-foreground">
                Request ID: {error.requestId}
              </span>
            )}
          </p>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={deleting}>Cancel</AlertDialogCancel>
          {/* A plain Button, not AlertDialogAction: the dialog must stay open while deleting. */}
          <Button
            onClick={confirm}
            disabled={deleting}
            className="bg-danger text-white hover:bg-danger/90 focus-visible:ring-danger/40"
          >
            {deleting ? "Deleting…" : "Delete document"}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
