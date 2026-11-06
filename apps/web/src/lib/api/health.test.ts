import { describe, expect, it } from "vitest";

import { parseReadyResponse } from "./health";

describe("parseReadyResponse", () => {
  it("accepts a valid payload and normalises optional fields", () => {
    const parsed = parseReadyResponse({
      status: "degraded",
      checks: [
        { name: "postgres", state: "ok", required: true, detail: "PostgreSQL 16.15" },
        {
          name: "embedding_model",
          state: "missing",
          required: false,
          detail: "not installed",
          remediation: "ollama pull nomic-embed-text:v1.5",
          latency_ms: null,
        },
      ],
    });
    expect(parsed.checks[0]).toMatchObject({ remediation: null, latency_ms: null });
    expect(parsed.checks[1].remediation).toBe("ollama pull nomic-embed-text:v1.5");
  });

  it.each([
    ["null", null],
    ["unknown status", { status: "great", checks: [] }],
    ["checks not an array", { status: "ready", checks: {} }],
    ["unknown check state", { status: "ready", checks: [{ name: "x", state: "?", detail: "" }] }],
    ["missing name", { status: "ready", checks: [{ state: "ok", detail: "" }] }],
  ])("rejects %s", (_label, raw) => {
    expect(() => parseReadyResponse(raw)).toThrow(TypeError);
  });
});
