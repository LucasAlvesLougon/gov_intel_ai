import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearSession,
  getAccessToken,
  getCurrentUser,
  setAccessToken,
  setCurrentUser,
  authStore,
} from "../lib/auth";
import { ApiClientError, apiRequest } from "../lib/http";

describe("Frontend Auth Store & HTTP Client (Task 23)", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://localhost:8000";
    clearSession();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    clearSession();
  });

  it("stores accessToken and user strictly in memory and does not write to localStorage", () => {
    const mockUser = {
      id: "u-123",
      email: "test@example.com",
      role: "OWNER",
      companyId: "c-123",
      isActive: true,
      createdAt: "2026-09-16T00:00:00Z",
    };

    setAccessToken("sample-in-memory-token");
    setCurrentUser(mockUser);

    expect(getAccessToken()).toBe("sample-in-memory-token");
    expect(getCurrentUser()).toEqual(mockUser);

    clearSession();
    expect(getAccessToken()).toBeNull();
    expect(getCurrentUser()).toBeNull();
  });

  it("attaches Authorization header with Bearer token on authenticated requests", async () => {
    setAccessToken("test-bearer-token");

    const fetcher = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ user: { id: "u-1" }, company: { id: "c-1" } }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetcher);

    await apiRequest("/api/auth/me/");

    expect(fetcher).toHaveBeenCalledTimes(1);
    const headers = fetcher.mock.calls[0][1]?.headers as Record<string, string>;
    expect(headers?.["Authorization"]).toBe("Bearer test-bearer-token");
  });

  it("attaches X-CSRFToken header on mutating requests (POST, PUT, DELETE)", async () => {
    // 1st call for CSRF token
    const fetcher = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/auth/csrf/")) {
        return Promise.resolve(
          new Response(JSON.stringify({ csrfToken: "csrf-secret-123" }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      return Promise.resolve(
        new Response(JSON.stringify({ success: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });
    vi.stubGlobal("fetch", fetcher);

    await apiRequest("/api/test-mutation/", {
      method: "POST",
      body: JSON.stringify({}),
    });

    // Should have requested CSRF first and then attached it to POST
    expect(fetcher).toHaveBeenCalledTimes(2);
    const postCallHeaders = fetcher.mock.calls[1][1]?.headers as Record<
      string,
      string
    >;
    expect(postCallHeaders?.["X-CSRFToken"]).toBe("csrf-secret-123");
  });

  it("parses error envelopes { error: { code, message, details } } into ApiClientError", async () => {
    const errorBody = {
      error: {
        code: "VALIDATION_ERROR",
        message: "Email inválido.",
        details: { email: ["Formato incorreto."] },
      },
    };

    const fetcher = vi.fn().mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify(errorBody), {
          status: 400,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    vi.stubGlobal("fetch", fetcher);

    await expect(apiRequest("/api/test-endpoint/")).rejects.toThrow(
      ApiClientError,
    );

    try {
      await apiRequest("/api/test-endpoint/");
    } catch (err) {
      const apiErr = err as ApiClientError;
      expect(apiErr.statusCode).toBe(400);
      expect(apiErr.code).toBe("VALIDATION_ERROR");
      expect(apiErr.message).toBe("Email inválido.");
      expect(apiErr.details).toEqual({ email: ["Formato incorreto."] });
    }
  });

  it("handles 401 transparently with automatic token refresh and retries the request", async () => {
    setAccessToken("expired-token");

    let callCount = 0;
    const fetcher = vi.fn().mockImplementation((url: string) => {
      callCount++;
      if (url.includes("/api/auth/csrf/")) {
        return Promise.resolve(
          new Response(JSON.stringify({ csrfToken: "csrf-test" }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      if (url.includes("/api/auth/token/refresh/")) {
        return Promise.resolve(
          new Response(JSON.stringify({ accessToken: "refreshed-new-token" }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      if (callCount === 1) {
        // First request with expired token -> 401
        return Promise.resolve(
          new Response(
            JSON.stringify({
              error: {
                code: "AUTHENTICATION_FAILED",
                message: "Token expirado.",
                details: {},
              },
            }),
            { status: 401, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      // Retry request with refreshed token -> 200
      return Promise.resolve(
        new Response(JSON.stringify({ data: "secret-data" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });
    vi.stubGlobal("fetch", fetcher);

    const result = await apiRequest<{ data: string }>("/api/tenders/");

    expect(result).toEqual({ data: "secret-data" });
    expect(getAccessToken()).toBe("refreshed-new-token");
    expect(fetcher).toHaveBeenCalledTimes(4); // 1. Original (401), 2. CSRF (200), 3. Refresh (200), 4. Retry (200)
  });

  it("clears session and fails when 401 refresh fails", async () => {
    setAccessToken("expired-token");

    const fetcher = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/auth/token/refresh/")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              error: {
                code: "AUTHENTICATION_FAILED",
                message: "Refresh token inválido.",
                details: {},
              },
            }),
            { status: 401, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({
            error: {
              code: "AUTHENTICATION_FAILED",
              message: "Token expirado.",
              details: {},
            },
          }),
          { status: 401, headers: { "Content-Type": "application/json" } },
        ),
      );
    });
    vi.stubGlobal("fetch", fetcher);

    await expect(apiRequest("/api/tenders/")).rejects.toThrow(ApiClientError);
    expect(getAccessToken()).toBeNull();
  });

  it("never leaks tokens in ApiClientError string representation", async () => {
    setAccessToken("super-secret-token-12345");

    const fetcher = vi
      .fn()
      .mockResolvedValue(new Response("Server Error", { status: 500 }));
    vi.stubGlobal("fetch", fetcher);

    try {
      await apiRequest("/api/tenders/");
    } catch (err) {
      const str = String(err);
      expect(str).not.toContain("super-secret-token-12345");
    }
  });

  it("authStore provides login, register, logout and me helpers", async () => {
    const mockAuthResponse = {
      accessToken: "token-auth-123",
      user: {
        id: "u-1",
        email: "owner@empresa.com",
        role: "OWNER",
        companyId: "c-1",
        isActive: true,
        createdAt: "2026-09-16T00:00:00Z",
      },
      company: {
        id: "c-1",
        name: "Empresa Teste",
        slug: "empresa-teste-abc",
        createdAt: "2026-09-16T00:00:00Z",
      },
    };

    const fetcher = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/auth/csrf/")) {
        return Promise.resolve(
          new Response(JSON.stringify({ csrfToken: "csrf-1" }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      if (
        url.includes("/api/auth/login/") ||
        url.includes("/api/auth/token/")
      ) {
        return Promise.resolve(
          new Response(JSON.stringify(mockAuthResponse), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      if (url.includes("/api/auth/logout/")) {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      return Promise.resolve(new Response(null, { status: 404 }));
    });
    vi.stubGlobal("fetch", fetcher);

    // Login
    const loginRes = await authStore.login({
      email: "owner@empresa.com",
      password: "Password123!",
    });
    expect(loginRes.accessToken).toBe("token-auth-123");
    expect(getAccessToken()).toBe("token-auth-123");
    expect(getCurrentUser()?.email).toBe("owner@empresa.com");

    // Logout
    await authStore.logout();
    expect(getAccessToken()).toBeNull();
    expect(getCurrentUser()).toBeNull();
  });
});
