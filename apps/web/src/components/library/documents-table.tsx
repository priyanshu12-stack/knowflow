"use client";

import { EllipsisVertical, File, FileCode, FileText, FileType, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  formatBytes,
  type FileType as DocFileType,
  type LibraryDocument,
} from "@/lib/api/documents";

import { DocumentStatusBadge } from "./document-status";

// DRD §7.2: document-type icons, not colourful thumbnails.
const TYPE_ICON = { pdf: FileText, docx: FileType, txt: File, md: FileCode } as const;
const TYPE_LABEL: Record<DocFileType, string> = {
  pdf: "PDF",
  docx: "Word",
  txt: "Text",
  md: "Markdown",
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/** "—" with an accessible explanation for values that don't exist yet. */
function NotYet({ reason }: { reason: string }) {
  return (
    <span className="text-muted-foreground" title={reason}>
      <span aria-hidden="true">—</span>
      <span className="sr-only">{reason}</span>
    </span>
  );
}

export function DocumentsTable({
  documents,
  onDelete,
}: {
  documents: LibraryDocument[];
  onDelete: (doc: LibraryDocument) => void;
}) {
  return (
    <Table className="min-w-[720px] text-[14px]">
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="pl-5">Name</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="text-right">Pages</TableHead>
          <TableHead className="text-right">Chunks</TableHead>
          <TableHead>Uploaded</TableHead>
          <TableHead className="w-12 pr-5">
            <span className="sr-only">Actions</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {documents.map((doc) => {
          const Icon = TYPE_ICON[doc.fileType];
          return (
            <TableRow key={doc.id}>
              <TableCell className="max-w-[360px] py-3 pl-5 whitespace-normal">
                <div className="flex items-start gap-2.5">
                  <Icon
                    aria-hidden="true"
                    className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                    strokeWidth={1.75}
                  />
                  <div className="min-w-0">
                    <p className="truncate font-medium" title={doc.name}>
                      {doc.name}
                    </p>
                    <p className="text-[12px] text-muted-foreground tabular-nums">
                      {TYPE_LABEL[doc.fileType]} · {formatBytes(doc.sizeBytes)}
                      {doc.version > 1 && ` · version ${doc.version}`}
                    </p>
                    {doc.lastError && (
                      <p className="mt-1 text-[13px]">
                        <span className="sr-only">Error: </span>
                        {doc.lastError.message}
                      </p>
                    )}
                  </div>
                </div>
              </TableCell>
              <TableCell>
                <DocumentStatusBadge status={doc.status} />
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {doc.pageCount ?? <NotYet reason="Counted after text extraction" />}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {doc.chunkCount ?? <NotYet reason="Counted after chunking" />}
              </TableCell>
              <TableCell className="text-muted-foreground tabular-nums">
                <time dateTime={doc.createdAt}>{formatDate(doc.createdAt)}</time>
              </TableCell>
              <TableCell className="pr-5">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${doc.name}`}>
                      <EllipsisVertical aria-hidden="true" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem variant="destructive" onSelect={() => onDelete(doc)}>
                      <Trash2 aria-hidden="true" />
                      Delete…
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
