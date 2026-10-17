/**
 * Stable error shape returned by every backend endpoint:
 *   {"code": string, "message": string, "trace_id": string|null}
 */
export interface ApiErrorPayload {
  code: string;
  message: string;
  trace_id: string | null;
}

export class ApiError extends Error {
  readonly code: string;
  readonly traceId: string | null;
  readonly status: number;

  constructor(code: string, message: string, status = 0, traceId: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.traceId = traceId;
    this.status = status;
  }

  static fromPayload(payload: Partial<ApiErrorPayload>, status = 0): ApiError {
    return new ApiError(
      payload.code ?? "UNKNOWN_ERROR",
      payload.message ?? "An unknown error occurred.",
      status,
      payload.trace_id ?? null,
    );
  }

  /** True for the graceful-empty-state cases (e.g. v1 endpoints not implemented yet). */
  get isNotFound(): boolean {
    return this.status === 404 || this.code.endsWith("_NOT_FOUND");
  }

  get isNetwork(): boolean {
    return this.status === 0;
  }
}
