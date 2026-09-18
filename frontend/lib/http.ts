import {
  clearSession,
  ensureCsrfToken,
  getAccessToken,
  refreshAccessToken,
} from "./auth";
import { getApiBaseUrl } from "./api-url";
import { ApiErrorResponse } from "./types";

export class ApiClientError extends Error {
  readonly statusCode: number;
  readonly code: string;
  readonly details: Record<string, unknown> | Array<unknown>;

  constructor(
    statusCode: number,
    code: string,
    message: string,
    details: Record<string, unknown> | Array<unknown> = {},
  ) {
    super(message);
    this.name = "ApiClientError";
    this.statusCode = statusCode;
    this.code = code;
    this.details = details;
  }
}

interface ApiRequestOptions extends RequestInit {
  requiresAuth?: boolean;
  skipAutoRefresh?: boolean;
  /** Timeout em ms por requisição (default: NEXT_PUBLIC_API_TIMEOUT_MS ou 15000). */
  timeoutMs?: number;
}

const DEFAULT_TIMEOUT_MS = Number(
  process.env.NEXT_PUBLIC_API_TIMEOUT_MS ?? 15000,
);

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const base = getApiBaseUrl();
  const origin = new URL(base);
  const url = new URL(path, origin);
  if (!path.startsWith("/") || url.origin !== origin.origin) {
    throw new Error("Caminho de API inválido.");
  }

  const method = (options.method || "GET").toUpperCase();
  const headers: Record<string, string> = {};

  if (options.headers) {
    if (options.headers instanceof Headers) {
      options.headers.forEach((v, k) => {
        headers[k] = v;
      });
    } else if (Array.isArray(options.headers)) {
      options.headers.forEach(([k, v]) => {
        headers[k] = v;
      });
    } else {
      Object.assign(headers, options.headers);
    }
  }

  // 1. Injetar CSRF Token em mutações de estado (POST, PUT, PATCH, DELETE)
  const isMutation = ["POST", "PUT", "PATCH", "DELETE"].includes(method);
  if (
    isMutation &&
    !headers["X-CSRFToken"] &&
    !path.includes("/api/auth/csrf/")
  ) {
    try {
      const csrf = await ensureCsrfToken();
      if (csrf) {
        headers["X-CSRFToken"] = csrf;
      }
    } catch {
      // Prossegue caso a obtenção de CSRF falhe ou seja mockada
    }
  }

  // 2. Injetar Authorization Bearer se access token existir em memória
  const token = getAccessToken();
  if (token && !headers["Authorization"]) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // 3. Definir Content-Type se corpo presente e não definido
  if (
    options.body &&
    typeof options.body === "string" &&
    !headers["Content-Type"]
  ) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(url.toString(), {
    ...options,
    method,
    headers,
    credentials: "include",
    cache: "no-store",
    signal:
      options.signal ??
      AbortSignal.timeout(options.timeoutMs ?? DEFAULT_TIMEOUT_MS),
  });

  // 4. Tratamento de 401 com auto-refresh transparente
  const isAuthEndpoint =
    path.includes("/api/auth/token/") ||
    path.includes("/api/auth/token/refresh/") ||
    path.includes("/api/auth/register/");

  if (
    response.status === 401 &&
    !options.skipAutoRefresh &&
    !isAuthEndpoint &&
    token
  ) {
    try {
      const newToken = await refreshAccessToken();
      if (newToken) {
        // Retry da requisição original com o novo access token
        return apiRequest<T>(path, {
          ...options,
          skipAutoRefresh: true,
        });
      }
    } catch {
      clearSession();
    }
  }

  if (!response.ok) {
    let errorCode = "API_ERROR";
    let errorMessage = "Não foi possível concluir a solicitação.";
    let errorDetails: Record<string, unknown> | Array<unknown> = {};

    try {
      const errorJson = (await response.json()) as ApiErrorResponse;
      if (errorJson && errorJson.error) {
        errorCode = errorJson.error.code || errorCode;
        errorMessage = errorJson.error.message || errorMessage;
        errorDetails = errorJson.error.details || errorDetails;
      }
    } catch {
      // Resposta não-JSON ou erro genérico de rede/upstream
    }

    throw new ApiClientError(
      response.status,
      errorCode,
      errorMessage,
      errorDetails,
    );
  }

  if (response.status === 204) {
    return null as T;
  }

  return (await response.json()) as T;
}
