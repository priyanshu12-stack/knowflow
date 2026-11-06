import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, getJson } from "./client";

const identity = (raw: unknown) => raw;

function mockFetch(impl: () => Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn(impl));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("getJson", () => {
  it("returns parsed data and request id on 2xx", async () => {
    mockFetch(async () =>
      Response.json({ status: "ok" }, { headers: { "X-Request-ID": "req-1" } }),
    );
    const res = await getJson("/x", identity);
    expect(res).toEqual({ status: 200, data: { status: "ok" }, requestId: "req-1" });
  });

  it("treats accepted non-2xx statuses as data", async () => {
    mockFetch(async () => Response.json({ status: "not_ready" }, { status: 503 }));
    const res = await getJson("/x", identity, { acceptStatuses: [503] });
    expect(res.status).toBe(503);
  });

  it("maps the API error envelope to ApiError", async () => {
    mockFetch(async () =>
      Response.json(
        { error: { code: "not_found", message: "Missing.", request_id: "req-2" } },
        { status: 404 },
      ),
    );
    await expect(getJson("/x", identity)).rejects.toMatchObject({
      code: "not_found",
      message: "Missing.",
      status: 404,
      requestId: "req-2",
    });
  });

  it("reports api_unreachable on network failure", async () => {
    mockFetch(async () => {
      throw new TypeError("fetch failed");
    });
    await expect(getJson("/x", identity)).rejects.toMatchObject({ code: "api_unreachable" });
  });

  it("reports api_unreachable when the proxy returns a non-envelope 500", async () => {
    mockFetch(async () => new Response("Internal Server Error", { status: 500 }));
    await expect(getJson("/x", identity)).rejects.toMatchObject({ code: "api_unreachable" });
  });

  it("rejects payloads that fail validation", async () => {
    mockFetch(async () => Response.json({ unexpected: true }));
    const strict = () => {
      throw new TypeError("bad");
    };
    const err = await getJson("/x", strict).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).code).toBe("invalid_response");
  });
});
