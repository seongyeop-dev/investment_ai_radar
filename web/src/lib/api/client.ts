import type { ApiErrorResponse } from "@/types/api";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
const DEFAULT_TIMEOUT_MS = 10_000;

export type ApiErrorKind =
  | "api"
  | "network"
  | "timeout"
  | "cancelled"
  | "invalid-response";

export class ApiClientError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  readonly code: string;
  readonly details: ApiErrorResponse["error"]["details"];

  constructor({
    message,
    kind,
    code,
    status = null,
    details = {},
  }: {
    message: string;
    kind: ApiErrorKind;
    code: string;
    status?: number | null;
    details?: ApiErrorResponse["error"]["details"];
  }) {
    super(message);
    this.name = "ApiClientError";
    this.kind = kind;
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

function normalizeBaseUrl(value: string | undefined): string {
  const trimmed = value?.trim() || DEFAULT_API_BASE_URL;
  return trimmed.replace(/\/+$/, "");
}

const CONFIGURED_API_BASE_URL = normalizeBaseUrl(
  process.env.NEXT_PUBLIC_API_BASE_URL,
);

export function resolveApiBaseUrl(
  hostname?: string,
  port?: string,
  protocol?: string,
): string {
  const currentHostname =
    hostname ??
    (typeof window === "undefined"
      ? ""
      : window.location.hostname);

  const currentPort =
    port ??
    (typeof window === "undefined"
      ? ""
      : window.location.port);

  const currentProtocol =
    protocol ??
    (typeof window === "undefined"
      ? "http:"
      : window.location.protocol);

  const normalizedProtocol =
    currentProtocol.endsWith(":")
      ? currentProtocol
      : `${currentProtocol}:`;

  if (currentHostname && currentPort === "3000") {
    return `${normalizedProtocol}//${currentHostname}:8000`;
  }

  if (currentHostname && currentPort === "3001") {
    return `${normalizedProtocol}//${currentHostname}:8001`;
  }

  return CONFIGURED_API_BASE_URL;
}

function isApiErrorResponse(value: unknown): value is ApiErrorResponse {
  if (!value || typeof value !== "object" || !("error" in value)) {
    return false;
  }
  const error = (value as { error?: unknown }).error;
  return Boolean(
    error &&
      typeof error === "object" &&
      "code" in error &&
      "message" in error &&
      typeof (error as { code: unknown }).code === "string" &&
      typeof (error as { message: unknown }).message === "string",
  );
}

interface FastApiDetailErrorResponse {
  detail: {
    code: string;
    message: string;
    [key: string]: unknown;
  };
}

function isFastApiDetailErrorResponse(
  value: unknown,
): value is FastApiDetailErrorResponse {
  if (
    !value ||
    typeof value !== "object" ||
    !("detail" in value)
  ) {
    return false;
  }

  const detail = (
    value as {
      detail?: unknown;
    }
  ).detail;

  return Boolean(
    detail &&
      typeof detail === "object" &&
      "code" in detail &&
      "message" in detail &&
      typeof (
        detail as {
          code: unknown;
        }
      ).code === "string" &&
      typeof (
        detail as {
          message: unknown;
        }
      ).message === "string",
  );
}

async function parseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    throw new ApiClientError({
      message: "서버 응답 형식을 확인할 수 없습니다.",
      kind: "invalid-response",
      code: "INVALID_RESPONSE",
      status: response.status,
    });
  }
}

export async function requestJson<T>(
  path: string,
  init: RequestInit & { timeoutMs?: number } = {},
): Promise<T> {
  const controller = new AbortController();
  const timeoutMs = init.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  let timedOut = false;
  const externalSignal = init.signal;
  const abortFromExternal = () => controller.abort(externalSignal?.reason);
  externalSignal?.addEventListener("abort", abortFromExternal, { once: true });
  const timeout = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  try {
    const response = await fetch(`${resolveApiBaseUrl()}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
    });
    if (response.status === 204) {
      return undefined as T;
    }
    const body = await parseBody(response);
    if (!response.ok) {
      if (isApiErrorResponse(body)) {
        throw new ApiClientError({
          message: body.error.message,
          kind: "api",
          code: body.error.code,
          status: response.status,
          details: body.error.details,
        });
      }

      if (
        isFastApiDetailErrorResponse(body)
      ) {
        const {
          code,
          message,
          ...details
        } = body.detail;

        throw new ApiClientError({
          message,
          kind: "api",
          code,
          status: response.status,
          details,
        });
      }

      throw new ApiClientError({
        message: "서버 요청을 처리하지 못했습니다.",
        kind: "api",
        code: "HTTP_ERROR",
        status: response.status,
      });
    }
    return body as T;
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }
    if (externalSignal?.aborted) {
      throw new ApiClientError({
        message: "요청이 취소되었습니다.",
        kind: "cancelled",
        code: "REQUEST_CANCELLED",
      });
    }
    if (timedOut) {
      throw new ApiClientError({
        message: "서버 응답 시간이 초과되었습니다. 다시 시도해 주세요.",
        kind: "timeout",
        code: "REQUEST_TIMEOUT",
      });
    }
    throw new ApiClientError({
      message: "서버에 연결할 수 없습니다. 실행 상태를 확인해 주세요.",
      kind: "network",
      code: "NETWORK_ERROR",
    });
  } finally {
    window.clearTimeout(timeout);
    externalSignal?.removeEventListener("abort", abortFromExternal);
  }
}

export function getFieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiClientError)) {
    return {};
  }
  const issues = error.details.issues;
  if (!Array.isArray(issues)) {
    return {};
  }
  return Object.fromEntries(
    issues
      .filter(
        (issue) =>
          issue &&
          typeof issue === "object" &&
          Array.isArray(issue.location) &&
          typeof issue.message === "string",
      )
      .map((issue) => [
        issue.location[issue.location.length - 1] ?? "form",
        issue.message,
      ]),
  );
}
