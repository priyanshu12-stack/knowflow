import { StatusBadge, type StatusTone } from "@/components/ui/status-badge";
import type { DocumentStatus } from "@/lib/api/documents";

const DISPLAY: Record<DocumentStatus, { tone: StatusTone; label: string }> = {
  queued: { tone: "neutral", label: "Queued" },
  extracting: { tone: "pending", label: "Extracting" },
  chunking: { tone: "pending", label: "Chunking" },
  embedding: { tone: "pending", label: "Embedding" },
  ready: { tone: "ok", label: "Ready" },
  failed: { tone: "danger", label: "Failed" },
};

/** PRD §5.2 document states as DRD §8 status badges (icon + text). */
export function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  const { tone, label } = DISPLAY[status];
  return <StatusBadge tone={tone}>{label}</StatusBadge>;
}

export function documentStatusLabel(status: DocumentStatus): string {
  return DISPLAY[status].label;
}
