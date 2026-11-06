import { describe, expect, it } from "vitest";

import { ApiError } from "./client";
import {
  duplicateOf,
  extensionOf,
  formatBytes,
  parseDocument,
  parseDocumentPage,
  parseUploadPolicy,
  precheckFile,
} from "./documents";

import { RAW_DOC, RAW_POLICY } from "@/test/fixtures";

describe("documents API parsing", () => {
  it("maps snake_case API documents to the UI model", () => {
    const doc = parseDocument(RAW_DOC);
    expect(doc.name).toBe("Leave Policy.pdf");
    expect(doc.chunkCount).toBeNull();
    expect(doc.latestJob?.status).toBe("queued");
  });

  it("rejects documents with an unknown status", () => {
    expect(() => parseDocument({ ...RAW_DOC, status: "done" })).toThrow();
  });

  it("parses pages and upload policies", () => {
    const page = parseDocumentPage({ items: [RAW_DOC], total: 1, limit: 25, offset: 0 });
    expect(page.items).toHaveLength(1);
    expect(parseUploadPolicy(RAW_POLICY).formats[1].extensions).toContain(".markdown");
  });

  it("extracts the existing document from a duplicate error only", () => {
    const dup = new ApiError("duplicate_document", "dup", 409, "r1", {
      existing_document: RAW_DOC,
    });
    expect(duplicateOf(dup)?.id).toBe("d1");
    expect(duplicateOf(new ApiError("other", "x", 400, null))).toBeNull();
  });
});

describe("precheckFile", () => {
  const policy = parseUploadPolicy(RAW_POLICY);
  const file = (name: string, size: number) => new File([new Uint8Array(size)], name);

  it("accepts supported, non-empty files under the limit", () => {
    expect(precheckFile(file("notes.MD", 10), policy)).toBeNull();
  });

  it("rejects unsupported types, empty files and oversized files", () => {
    expect(precheckFile(file("virus.exe", 10), policy)).toMatch(/isn't supported/);
    expect(precheckFile(file("empty.pdf", 0), policy)).toBe("The file is empty.");
    const big = { name: "big.pdf", size: policy.maxBytes + 1 } as File;
    expect(precheckFile(big, policy)).toMatch(/25 MB limit/);
  });

  it("derives extensions and byte labels", () => {
    expect(extensionOf("a.b.PDF")).toBe(".pdf");
    expect(extensionOf(".env")).toBe("");
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(1536)).toBe("1.5 KB");
  });
});
