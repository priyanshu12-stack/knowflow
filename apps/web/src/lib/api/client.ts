/**
 * Minimal typed client for the KnowFlow API. The browser always calls same-origin `/api/v1/*`;
 * next.config.ts rewrites those requests to FastAPI.
 */

export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number | null,
    readonly requestId: string | null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface ErrorEnvelope {
  error: { code: string; message: string; request_id?: string };
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

export interface ApiResponse<T> {
  status: number;
  data: T;
  requestId: string | null;
}

/**
 * GET JSON. `acceptStatuses` lets callers treat documented non-2xx bodies (e.g. readiness 503)
 * as data rather than errors.
 */
export async function getJson<T>(
  path: string,
  parse: (raw: unknown) => T,
  {
    timeoutMs = 10_000,
    acceptStatuses = [] as number[],
    signal,
  }: {
    timeoutMs?: number;
    acceptStatuses?: number[];
    signal?: AbortSignal;
  } = {},
): Promise<ApiResponse<T>> {
  const timeout = AbortSignal.timeout(timeoutMs);
  const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;

  let res: Response;
  try {
    res = await fetch(path, { headers: { Accept: "application/json" }, signal: combined });
  } catch (cause) {
    if (timeout.aborted) {
      throw new ApiError("timeout", "The KnowFlow API did not respond in time.", null, null);
    }
    if (signal?.aborted) throw cause;
    throw new ApiError("api_unreachable", "The KnowFlow API is not reachable.", null, null);
  }

  const requestId = res.headers.get("X-Request-ID");
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    // Non-JSON body (e.g. proxy error page); handled below.
  }

  if (res.ok || acceptStatuses.includes(res.status)) {
    try {
      return { status: res.status, data: parse(body), requestId };
    } catch {
      throw new ApiError(
        "invalid_response",
        "The API returned data in an unexpected format.",
        res.status,
        requestId,
      );
    }
  }
  if (isErrorEnvelope(body)) {
    throw new ApiError(
      body.error.code,
      body.error.message,
      res.status,
      body.error.request_id ?? requestId,
    );
  }
  // Next's proxy answers 500 without our envelope when FastAPI is down.
  throw new ApiError(
    res.status >= 500 ? "api_unreachable" : "http_error",
    res.status >= 500 ? "The KnowFlow API is not reachable." : `Request failed (${res.status}).`,
    res.status,
    requestId,
  );
}
