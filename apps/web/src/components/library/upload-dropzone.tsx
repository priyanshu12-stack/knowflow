"use client";

import { Upload } from "lucide-react";
import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { formatBytes, type UploadPolicy } from "@/lib/api/documents";
import { cn } from "@/lib/utils";

/**
 * DRD §7.2 / §8 upload dropzone: compact, bordered, shows supported types and the size limit
 * before a file is chosen. Idle and drag-over live here; uploading / rejected / complete are
 * shown per file in the upload queue.
 */
export function UploadDropzone({
  policy,
  onFiles,
  inputRef,
}: {
  policy: UploadPolicy;
  onFiles: (files: File[]) => void;
  inputRef: React.RefObject<HTMLInputElement | null>;
}) {
  const [dragOver, setDragOver] = useState(false);
  const hintId = useId();
  const accept = policy.formats.flatMap((f) => f.extensions).join(",");
  const types = policy.formats.map((f) => f.label).join(", ");

  return (
    <div
      onDragEnter={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragOver={(e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "copy";
      }}
      onDragLeave={(e) => {
        // Only leave when the pointer exits the zone, not when it crosses a child element.
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDragOver(false);
      }}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        const files = Array.from(e.dataTransfer.files);
        if (files.length > 0) onFiles(files);
      }}
      data-state={dragOver ? "drag-over" : "idle"}
      className={cn(
        "flex flex-col items-start gap-3 rounded-xl border border-dashed bg-card px-5 py-4 transition-colors sm:flex-row sm:items-center",
        dragOver && "border-primary bg-accent",
      )}
    >
      <Upload aria-hidden="true" className="size-5 shrink-0 text-primary" strokeWidth={1.75} />
      <div className="min-w-0 flex-1">
        <p className="font-medium">
          {dragOver ? "Drop to upload" : "Drag files here, or choose them from your computer"}
        </p>
        <p id={hintId} className="text-[13px] text-muted-foreground">
          {types} · up to {formatBytes(policy.maxBytes)} each. Scanned PDFs without a text layer
          aren&apos;t supported.
        </p>
      </div>
      <Button variant="outline" size="sm" onClick={() => inputRef.current?.click()}>
        Choose files
      </Button>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={accept}
        aria-describedby={hintId}
        aria-label="Choose documents to upload"
        className="sr-only"
        tabIndex={-1}
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          e.target.value = ""; // allow choosing the same file again
          if (files.length > 0) onFiles(files);
        }}
      />
    </div>
  );
}
