/** Shared API payloads for tests, in the exact snake_case shape the API returns. */
export const RAW_DOC = {
  id: "d1",
  original_name: "Leave Policy.pdf",
  file_type: "pdf",
  mime_type: "application/pdf",
  size_bytes: 2048,
  sha256: "ab".repeat(32),
  version: 1,
  status: "queued",
  page_count: null,
  chunk_count: null,
  extracted_char_count: null,
  citation_granularity: null,
  last_error: null,
  latest_job: {
    id: "j1",
    document_id: "d1",
    status: "queued",
    stage: null,
    attempts: 0,
    error_code: null,
    error_message_safe: null,
    created_at: "2026-11-07T00:00:00+00:00",
    started_at: null,
    completed_at: null,
  },
  created_at: "2026-11-07T00:00:00+00:00",
  updated_at: "2026-11-07T00:00:00+00:00",
};

export const RAW_POLICY = {
  max_bytes: 25 * 1024 * 1024,
  formats: [
    { file_type: "pdf", label: "PDF", extensions: [".pdf"] },
    { file_type: "md", label: "Markdown", extensions: [".md", ".markdown"] },
  ],
};
