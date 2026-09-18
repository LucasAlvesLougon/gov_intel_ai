import {
  AuthResponse,
  Company,
  CsrfResponse,
  LoginPayload,
  MeResponse,
  RefreshResponse,
  RegisterPayload,
  User,
} from "./types";
import { getApiBaseUrl } from "./api-url";

// Estado estritamente em memória — NUNCA salvar access tokens no localStorage ou sessionStorage
let inMemoryAccessToken: string | null = null;
let inMemoryUser: User | null = null;
let inMemoryCompany: Company | null = null;
let inMemoryCsrfToken: string | null = null;
let refreshPromise: Promise<string> | null = null;

export function getAccessToken(): string | null {
  return inMemoryAccessToken;
}

export function setAccessToken(token: string | null): void {
  inMemoryAccessToken = token;
}

export function getCurrentUser(): User | null {
  return inMemoryUser;
}

export function setCurrentUser(user: User | null): void {
  inMemoryUser = user;
}

export function getCurrentCompany(): Company | null {
  return inMemoryCompany;
}

export function setCurrentCompany(company: Company | null): void {
  inMemoryCompany = company;
}

export function getCachedCsrfToken(): string | null {
  return inMemoryCsrfToken;
}

export function setCachedCsrfToken(token: string | null): void {
  inMemoryCsrfToken = token;
}

export function clearSession(): void {
  inMemoryAccessToken = null;
  inMemoryUser = null;
  inMemoryCompany = null;
  inMemoryCsrfToken = null;
  refreshPromise = null;
}

/**
 * Obtém ou renova o CSRF token a partir de GET /api/auth/csrf/
 */
export async function ensureCsrfToken(): Promise<string> {
  if (inMemoryCsrfToken) {
    return inMemoryCsrfToken;
  }
  const base = getApiBaseUrl();
  const res = await fetch(new URL("/api/auth/csrf/", base).toString(), {
    method: "GET",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    throw new Error("Não foi possível obter o token CSRF.");
  }
  const data = (await res.json()) as CsrfResponse;
  inMemoryCsrfToken = data.csrfToken;
  return inMemoryCsrfToken;
}

/**
 * Executa a renovação de access token via cookie httpOnly com proteção de concorrência (single-flight)
 */
export async function refreshAccessToken(): Promise<string> {
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    try {
      const base = getApiBaseUrl();

      const csrf = await ensureCsrfToken().catch(() => "");
      const res = await fetch(
        new URL("/api/auth/token/refresh/", base).toString(),
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            ...(csrf ? { "X-CSRFToken": csrf } : {}),
          },
        },
      );

      if (!res.ok) {
        clearSession();
        throw new Error("Sessão expirada. Faça login novamente.");
      }

      const data = (await res.json()) as RefreshResponse;
      inMemoryAccessToken = data.accessToken;
      return data.accessToken;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

export const authStore = {
  async register(payload: RegisterPayload): Promise<AuthResponse> {
    const { apiRequest } = await import("./http");
    const res = await apiRequest<AuthResponse>("/api/auth/register/", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setAccessToken(res.accessToken);
    setCurrentUser(res.user);
    setCurrentCompany(res.company);
    return res;
  },

  async login(payload: LoginPayload): Promise<AuthResponse> {
    const { apiRequest } = await import("./http");
    const res = await apiRequest<AuthResponse>("/api/auth/token/", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setAccessToken(res.accessToken);
    setCurrentUser(res.user);
    setCurrentCompany(res.company);
    return res;
  },

  async logout(): Promise<void> {
    const { apiRequest } = await import("./http");
    try {
      await apiRequest<null>("/api/auth/logout/", {
        method: "POST",
      });
    } finally {
      clearSession();
    }
  },

  async fetchMe(): Promise<MeResponse> {
    const { apiRequest } = await import("./http");
    const res = await apiRequest<MeResponse>("/api/auth/me/", {
      method: "GET",
    });
    setCurrentUser(res.user);
    setCurrentCompany(res.company);
    return res;
  },
};
