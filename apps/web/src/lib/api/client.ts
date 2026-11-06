/**
 * Minimal typed client for the KnowFlow API. The browser always calls same-origin `/api/v1/*`;
 * next.config.ts rewrites those requests to FastAPI. Every response body is validated by a
 * caller-supplied parser: API output is untrusted input.
 */

export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number | null,
    readonly requestId: string | null,
    /** Structured, user-safe context from the API (e.g. the existing document on a duplicate). */
    readonly details: Record<string, unknown> | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface ErrorEnvelope {
  error: { code: string; message: string; request_id?: string; details?: unknown };
}

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  if (typeof value !== "object" || value === null || !("error" in value)) return false;
  const err = (value as { error: unknown }).error;
  return (
    typeof err === "object" &&
    err !== null &&
    typeof (err as { code?: unknown }).code === "string" &&
    typeof (err as { message?: unknown }).message === "string"
  );
}

/** Turn a failed response (any transport) into an ApiError. */
export function toApiError(status: number, body: unknown, requestId: string | null): ApiError {
  if (isErrorEnvelope(body)) {
    const { details } = body.error;
    return new ApiError(
      body.error.code,
      body.error.message,
      status,
      body.error.request_id ?? requestId,
      typeof details === "object" && details !== null && !Array.isArray(details)
        ? (details as Record<string, unknown>)
        : null,
    );
  }
  // Next's proxy answers 500 without our envelope when FastAPI is down.
  return new ApiError(
    status >= 500 ? "api_unreachable" : "http_error",
    status >= 500 ? "The KnowFlow API is not reachable." : `Request failed (${status}).`,
    status,
    requestId,
  );
}

export function invalidResponse(status: number, requestId: string | null): ApiError {
  return new ApiError(
    "invalid_response",
    "The API returned data in an unexpected format.",
    status,
    requestId,
  );
}

export interface ApiResponse<T> {
  status: number;
  data: T;
  requestId: string | null;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  /** Serialized as a JSON request body. */
  json?: unknown;
  timeoutMs?: number;
  /** Documented non-2xx statuses whose body is data, not an error (e.g. readiness 503). */
  acceptStatuses?: number[];
  signal?: AbortSignal;
}

export async function requestJson<T>(
  path: string,
  parse: (raw: unknown) => T,
  { method = "GET", json, timeoutMs = 10_000, acceptStatuses = [], signal }: RequestOptions = {},
): Promise<ApiResponse<T>> {
  const timeout = AbortSignal.timeout(timeoutMs);
  const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (json !== undefined) headers["Content-Type"] = "application/json";

  let res: Response;
  try {
    res = await fetch(path, {
      method,
      headers,
      body: json === undefined ? undefined : JSON.stringify(json),
      signal: combined,
    });
  } catch (cause) {
    if (timeout.aborted) {
      throw new ApiError("timeout", "The KnowFlow API did not respond in time.", null, null);
    }
    if (signal?.aborted) throw cause;
    throw new ApiError("api_unreachable", "The KnowFlow API is not reachable.", null, null);
  }

  const requestId = res.headers.get("X-Request-ID");
  let body: unknown = null;
  if (res.status !== 204) {
    try {
      body = await res.json();
    } catch {
      // Non-JSON body (e.g. proxy error page); handled below.
    }
  }

  if (res.ok || acceptStatuses.includes(res.status)) {
    try {
      return { status: res.status, data: parse(body), requestId };
    } catch {
      throw invalidResponse(res.status, requestId);
    }
  }
  throw toApiError(res.status, body, requestId);
}

/** GET JSON (kept as the common case). */
export function getJson<T>(
  path: string,
  parse: (raw: unknown) => T,
  options: Omit<RequestOptions, "method" | "json"> = {},
): Promise<ApiResponse<T>> {
  return requestJson(path, parse, options);
}
