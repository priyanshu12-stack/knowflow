import { ApiError, invalidResponse, requestJson, toApiError } from "./client";
import { arr, fail, int, nullableInt, nullableStr, obj, oneOf, str, type Obj } from "./validate";

export const DOCUMENT_STATUSES = [
  "queued",
  "extracting",
  "chunking",
  "embedding",
  "ready",
  "failed",
] as const;
export type DocumentStatus = (typeof DOCUMENT_STATUSES)[number];

const JOB_STATUSES = ["queued", "running", "succeeded", "failed"] as const;
const JOB_STAGES = ["extracting", "chunking", "embedding"] as const;
const FILE_TYPES = ["pdf", "docx", "txt", "md"] as const;
const GRANULARITIES = ["page", "section", "document"] as const;
export type FileType = (typeof FILE_TYPES)[number];

export type DuplicateAction = "skip" | "reindex" | "new_version";

export interface IngestionJob {
  id: string;
  status: (typeof JOB_STATUSES)[number];
  stage: (typeof JOB_STAGES)[number] | null;
  attempts: number;
  errorMessage: string | null;
  createdAt: string;
}

export interface LibraryDocument {
  id: string;
  name: string;
  fileType: FileType;
  sizeBytes: number;
  sha256: string;
  version: number;
  status: DocumentStatus;
  pageCount: number | null;
  /** null = not processed yet, not zero chunks. */
  chunkCount: number | null;
  extractedCharCount: number | null;
  /** What a citation can point at: a page, a heading section, or only the whole document. */
  citationGranularity: "page" | "section" | "document" | null;
  lastError: { code: string; message: string } | null;
  latestJob: IngestionJob | null;
  createdAt: string;
  updatedAt: string;
}

export interface DocumentPage {
  items: LibraryDocument[];
  total: number;
  limit: number;
  offset: number;
}

export interface UploadPolicy {
  maxBytes: number;
  formats: { fileType: FileType; label: string; extensions: string[] }[];
}

export interface UploadResult {
  outcome: "created" | "new_version" | "reindexed" | "skipped";
  document: LibraryDocument;
}

function parseJob(raw: unknown, path: string): IngestionJob {
  const o = obj(raw, path);
  const stage = o.stage === null ? null : oneOf(o, "stage", JOB_STAGES, path);
  return {
    id: str(o, "id", path),
    status: oneOf(o, "status", JOB_STATUSES, path),
    stage,
    attempts: int(o, "attempts", path),
    errorMessage: nullableStr(o, "error_message_safe", path),
    createdAt: str(o, "created_at", path),
  };
}

export function parseDocument(raw: unknown, path = "document"): LibraryDocument {
  const o = obj(raw, path);
  let lastError: LibraryDocument["lastError"] = null;
  if (o.last_error !== null && o.last_error !== undefined) {
    const e = obj(o.last_error, `${path}.last_error`);
    lastError = { code: str(e, "code", path), message: str(e, "message", path) };
  }
  return {
    id: str(o, "id", path),
    name: str(o, "original_name", path),
    fileType: oneOf(o, "file_type", FILE_TYPES, path),
    sizeBytes: int(o, "size_bytes", path),
    sha256: str(o, "sha256", path),
    version: int(o, "version", path),
    status: oneOf(o, "status", DOCUMENT_STATUSES, path),
    pageCount: nullableInt(o, "page_count", path),
    chunkCount: nullableInt(o, "chunk_count", path),
    extractedCharCount: nullableInt(o, "extracted_char_count", path),
    citationGranularity:
      o.citation_granularity === null || o.citation_granularity === undefined
        ? null
        : oneOf(o, "citation_granularity", GRANULARITIES, path),
    lastError,
    latestJob: o.latest_job ? parseJob(o.latest_job, `${path}.latest_job`) : null,
    createdAt: str(o, "created_at", path),
    updatedAt: str(o, "updated_at", path),
  };
}

export function parseDocumentPage(raw: unknown): DocumentPage {
  const o = obj(raw, "page");
  return {
    items: arr(o, "items", "page", parseDocument),
    total: int(o, "total", "page"),
    limit: int(o, "limit", "page"),
    offset: int(o, "offset", "page"),
  };
}

export function parseUploadPolicy(raw: unknown): UploadPolicy {
  const o = obj(raw, "policy");
  return {
    maxBytes: int(o, "max_bytes", "policy"),
    formats: arr(o, "formats", "policy", (f, p) => {
      const fo = obj(f, p);
      return {
        fileType: oneOf(fo, "file_type", FILE_TYPES, p),
        label: str(fo, "label", p),
        extensions: arr(fo, "extensions", p, (e, ep) => {
          if (typeof e !== "string") fail(ep);
          return e;
        }),
      };
    }),
  };
}

export function parseUploadResult(raw: unknown): UploadResult {
  const o: Obj = obj(raw, "upload");
  return {
    outcome: oneOf(o, "outcome", ["created", "new_version", "reindexed", "skipped"], "upload"),
    document: parseDocument(o.document, "upload.document"),
  };
}

/** The existing document attached to a `duplicate_document` (409) error, if well-formed. */
export function duplicateOf(error: ApiError): LibraryDocument | null {
  if (error.code !== "duplicate_document" || !error.details) return null;
  try {
    return parseDocument(error.details.existing_document, "existing_document");
  } catch {
    return null;
  }
}

export async function fetchDocuments(
  { limit, offset, status }: { limit: number; offset: number; status?: DocumentStatus },
  signal?: AbortSignal,
) {
  const qs = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (status) qs.set("status", status);
  return (await requestJson(`/api/v1/documents?${qs}`, parseDocumentPage, { signal })).data;
}

export async function fetchUploadPolicy(signal?: AbortSignal) {
  return (await requestJson("/api/v1/documents/upload-policy", parseUploadPolicy, { signal })).data;
}

export async function retryDocument(id: string) {
  return (
    await requestJson(`/api/v1/documents/${encodeURIComponent(id)}/retry`, parseDocument, {
      method: "POST",
    })
  ).data;
}

export async function fetchDocument(id: string, signal?: AbortSignal) {
  return (
    await requestJson(`/api/v1/documents/${encodeURIComponent(id)}`, parseDocument, { signal })
  ).data;
}

export type ChunkStrategy = "fixed" | "recursive";

export interface DocumentChunk {
  id: string;
  index: number;
  text: string;
  pageStart: number | null;
  pageEnd: number | null;
  sectionPath: string | null;
  tokenCount: number;
}

export interface ChunkPage {
  items: DocumentChunk[];
  total: number;
}

export function parseChunkPage(raw: unknown): ChunkPage {
  const o = obj(raw, "chunks");
  return {
    total: int(o, "total", "chunks"),
    items: arr(o, "items", "chunks", (c, p) => {
      const co = obj(c, p);
      return {
        id: str(co, "id", p),
        index: int(co, "chunk_index", p),
        text: str(co, "text", p),
        pageStart: nullableInt(co, "page_start", p),
        pageEnd: nullableInt(co, "page_end", p),
        sectionPath: nullableStr(co, "section_path", p),
        tokenCount: int(co, "token_count", p),
      };
    }),
  };
}

export async function fetchChunks(
  id: string,
  { strategy, limit, offset }: { strategy: ChunkStrategy; limit: number; offset: number },
  signal?: AbortSignal,
) {
  const qs = new URLSearchParams({ strategy, limit: String(limit), offset: String(offset) });
  return (
    await requestJson(`/api/v1/documents/${encodeURIComponent(id)}/chunks?${qs}`, parseChunkPage, {
      signal,
    })
  ).data;
}

export interface ExtractionPreview {
  totalSections: number;
  sections: {
    ordinal: number;
    pageNumber: number | null;
    sectionPath: string | null;
    text: string;
  }[];
}

export function parseExtraction(raw: unknown): ExtractionPreview {
  const o = obj(raw, "extraction");
  return {
    totalSections: int(o, "total_sections", "extraction"),
    sections: arr(o, "sections", "extraction", (x, p) => {
      const so = obj(x, p);
      return {
        ordinal: int(so, "ordinal", p),
        pageNumber: nullableInt(so, "page_number", p),
        sectionPath: nullableStr(so, "section_path", p),
        text: str(so, "text", p),
      };
    }),
  };
}

export async function fetchExtraction(id: string, signal?: AbortSignal) {
  return (
    await requestJson(
      `/api/v1/documents/${encodeURIComponent(id)}/extraction?limit=3`,
      parseExtraction,
      { signal },
    )
  ).data;
}

/** Statuses where the worker is still expected to change something. */
export const IN_PROGRESS: readonly DocumentStatus[] = [
  "queued",
  "extracting",
  "chunking",
  "embedding",
];

export async function deleteDocument(id: string) {
  await requestJson(`/api/v1/documents/${encodeURIComponent(id)}`, () => undefined, {
    method: "DELETE",
  });
}

/** Lower-case extension including the dot, or "" when there is none. */
export function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(dot).toLowerCase() : "";
}

/** Client-side pre-check so obvious mistakes fail instantly. The API re-validates everything. */
export function precheckFile(file: File, policy: UploadPolicy): string | null {
  const allowed = policy.formats.flatMap((f) => f.extensions);
  if (!allowed.includes(extensionOf(file.name))) {
    return `This file type isn't supported. Upload one of: ${allowed.join(", ")}.`;
  }
  if (file.size === 0) return "The file is empty.";
  if (file.size > policy.maxBytes) {
    return `The file is larger than the ${formatBytes(policy.maxBytes)} limit.`;
  }
  return null;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value >= 10 || Number.isInteger(value) ? Math.round(value) : value.toFixed(1)} ${units[unit]}`;
}

/**
 * Upload one file. Uses XMLHttpRequest because fetch has no upload-progress events.
 * Resolves with the validated result; rejects with ApiError (409 carries the duplicate).
 */
export function uploadDocument(
  file: File,
  {
    onDuplicate,
    onProgress,
    signal,
  }: {
    onDuplicate?: DuplicateAction;
    onProgress?: (fraction: number) => void;
    signal?: AbortSignal;
  } = {},
): Promise<UploadResult> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const qs = onDuplicate ? `?on_duplicate=${onDuplicate}` : "";
    xhr.open("POST", `/api/v1/documents${qs}`);
    xhr.setRequestHeader("Accept", "application/json");
    xhr.responseType = "text";
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
    };
    xhr.onerror = () =>
      reject(new ApiError("api_unreachable", "The KnowFlow API is not reachable.", null, null));
    xhr.onabort = () => reject(new DOMException("Upload cancelled", "AbortError"));
    xhr.onload = () => {
      const requestId = xhr.getResponseHeader("X-Request-ID");
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        // handled below
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(parseUploadResult(body));
        } catch {
          reject(invalidResponse(xhr.status, requestId));
        }
        return;
      }
      reject(toApiError(xhr.status, body, requestId));
    };
    signal?.addEventListener("abort", () => xhr.abort(), { once: true });
    const form = new FormData();
    form.append("file", file, file.name);
    xhr.send(form);
  });
}
