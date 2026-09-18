/**
 * Task 25 — Dashboard e Upload com Polling
 * Testa: listagem de editais, upload multipart com Idempotency-Key, polling de status.
 *
 * Padrão: sem JSX; mocks de fetch globais; sem acesso a localStorage.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// ---------- helpers de mock ---------------------------------------------------
function mockFetch(responses: Array<{ status: number; body: unknown }>) {
  let call = 0;
  return vi.fn(async () => {
    const r = responses[call] ?? responses[responses.length - 1];
    call++;
    const body = r.body === null ? null : JSON.stringify(r.body);
    return {
      ok: r.status >= 200 && r.status < 300,
      status: r.status,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => (body ? JSON.parse(body) : null),
      text: async () => body ?? "",
    } as unknown as Response;
  });
}

const ENV_BASE = "http://api.test";

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", ENV_BASE);
  // reset in-memory token so auth doesn't auto-refresh
  vi.resetModules();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

// ---------- tenderApi.list ----------------------------------------------------
describe("tenderApi.list (Task 25)", () => {
  it("fetches GET /api/tenders/ and returns paginated response", async () => {
    const payload = {
      data: [
        {
          id: "t1",
          title: "Edital A",
          description: "Desc",
          status: "PENDING",
          fileSize: 1024,
          originalFilename: "a.pdf",
          createdAt: "2026-01-01T00:00:00Z",
          updatedAt: "2026-01-01T00:00:00Z",
        },
      ],
      pagination: { page: 1, pageSize: 20, totalItems: 1, totalPages: 1 },
    };

    const f = mockFetch([{ status: 200, body: payload }]);
    vi.stubGlobal("fetch", f);

    const { tenderApi } = await import("../lib/tenders");
    const result = await tenderApi.list({ page: 1, pageSize: 20 });
    expect(result.data).toHaveLength(1);
    expect(result.data[0].id).toBe("t1");
    expect(result.pagination.totalItems).toBe(1);
  });

  it("propagates ApiClientError on non-200 response", async () => {
    const f = mockFetch([
      {
        status: 401,
        body: {
          error: {
            code: "NOT_AUTHENTICATED",
            message: "Unauthorized",
            details: {},
          },
        },
      },
    ]);
    vi.stubGlobal("fetch", f);

    const { tenderApi } = await import("../lib/tenders");
    await expect(tenderApi.list({})).rejects.toMatchObject({ statusCode: 401 });
  });
});

// ---------- tenderApi.upload --------------------------------------------------
describe("tenderApi.upload (Task 25)", () => {
  it("sends multipart POST with Idempotency-Key header and returns 202 tender", async () => {
    const tenderPayload = {
      id: "t2",
      title: "Edital B",
      description: "Desc B",
      status: "PENDING",
      fileSize: 2048,
      originalFilename: "b.pdf",
      createdAt: "2026-01-01T00:00:00Z",
      updatedAt: "2026-01-01T00:00:00Z",
    };
    const f = mockFetch([
      { status: 200, body: { csrfToken: "csrf1" } }, // CSRF
      { status: 202, body: tenderPayload },
    ]);
    vi.stubGlobal("fetch", f);

    const { tenderApi } = await import("../lib/tenders");
    const file = new File(["fake-pdf-content"], "b.pdf", {
      type: "application/pdf",
    });
    const result = await tenderApi.upload({
      file,
      title: "Edital B",
      description: "Desc B",
      idempotencyKey: "idem-key-123",
    });

    expect(result.id).toBe("t2");
    expect(result.status).toBe("PENDING");

    // Verifica que o Idempotency-Key foi enviado
    const allCalls = f.mock.calls as unknown as Array<[string, RequestInit]>;
    const uploadCall = allCalls.find((c) => {
      const init = c[1];
      if (!init?.headers) return false;
      const h =
        init.headers instanceof Headers
          ? init.headers
          : new Headers(init.headers as Record<string, string>);
      return h.get("Idempotency-Key") === "idem-key-123";
    });
    expect(uploadCall).toBeTruthy();
  });

  it("does NOT set Content-Type on FormData (lets browser set boundary)", async () => {
    const f = mockFetch([
      { status: 200, body: { csrfToken: "csrf1" } },
      {
        status: 202,
        body: {
          id: "t3",
          title: "C",
          description: "",
          status: "PENDING",
          fileSize: 1,
          originalFilename: "c.pdf",
          createdAt: "2026-01-01T00:00:00Z",
          updatedAt: "2026-01-01T00:00:00Z",
        },
      },
    ]);
    vi.stubGlobal("fetch", f);

    const { tenderApi } = await import("../lib/tenders");
    const file = new File(["x"], "c.pdf", { type: "application/pdf" });
    await tenderApi.upload({
      file,
      title: "C",
      description: "",
      idempotencyKey: "k",
    });

    // O Content-Type não deve ser application/json (FormData)
    const allCalls2 = f.mock.calls as unknown as Array<[string, RequestInit]>;
    const uploadCall = allCalls2.find((c) => {
      const init = c[1];
      if (!init?.headers) return false;
      const h =
        init.headers instanceof Headers
          ? init.headers
          : new Headers(init.headers as Record<string, string>);
      return h.get("Idempotency-Key") !== null;
    });
    expect(uploadCall).toBeTruthy();
    if (uploadCall) {
      const init = uploadCall[1];
      const h =
        init.headers instanceof Headers
          ? init.headers
          : new Headers(init.headers as Record<string, string>);
      expect(h.get("Content-Type")).not.toBe("application/json");
    }
  });
});

// ---------- tenderApi.getStatus -----------------------------------------------
describe("tenderApi.getStatus (Task 25)", () => {
  it("fetches GET /api/tenders/{id}/processing-status/ and returns status", async () => {
    const status = {
      tenderId: "t1",
      status: "PROCESSING",
      progress: 50,
      processedChunks: 10,
      error: null,
    };
    const f = mockFetch([{ status: 200, body: status }]);
    vi.stubGlobal("fetch", f);

    const { tenderApi } = await import("../lib/tenders");
    const result = await tenderApi.getStatus("t1");
    expect(result.status).toBe("PROCESSING");
    expect(result.progress).toBe(50);
  });
});

// ---------- generateIdempotencyKey --------------------------------------------
describe("generateIdempotencyKey (Task 25)", () => {
  it("returns a non-empty string", async () => {
    const { generateIdempotencyKey } = await import("../lib/tenders");
    const key = generateIdempotencyKey();
    expect(typeof key).toBe("string");
    expect(key.length).toBeGreaterThan(8);
  });

  it("returns unique values on each call", async () => {
    const { generateIdempotencyKey } = await import("../lib/tenders");
    const a = generateIdempotencyKey();
    const b = generateIdempotencyKey();
    expect(a).not.toBe(b);
  });
});

// ---------- pollProcessingStatus ----------------------------------------------
describe("pollProcessingStatus (Task 25)", () => {
  it("resolves when terminal status PROCESSED is received", async () => {
    const responses = [
      {
        status: 200,
        body: {
          tenderId: "t1",
          status: "PENDING",
          progress: 0,
          processedChunks: 0,
          error: null,
        },
      },
      {
        status: 200,
        body: {
          tenderId: "t1",
          status: "PROCESSING",
          progress: 50,
          processedChunks: 5,
          error: null,
        },
      },
      {
        status: 200,
        body: {
          tenderId: "t1",
          status: "PROCESSED",
          progress: 100,
          processedChunks: 10,
          error: null,
        },
      },
    ];
    const f = mockFetch(responses);
    vi.stubGlobal("fetch", f);

    const { pollProcessingStatus } = await import("../lib/tenders");
    const result = await pollProcessingStatus("t1", {
      intervalMs: 0,
      maxAttempts: 10,
    });
    expect(result.status).toBe("PROCESSED");
  });

  it("resolves when terminal status FAILED is received", async () => {
    const responses = [
      {
        status: 200,
        body: {
          tenderId: "t1",
          status: "PROCESSING",
          progress: 30,
          processedChunks: 3,
          error: null,
        },
      },
      {
        status: 200,
        body: {
          tenderId: "t1",
          status: "FAILED",
          progress: 30,
          processedChunks: 3,
          error: { code: "PDF_INVALID", message: "PDF inválido" },
        },
      },
    ];
    const f = mockFetch(responses);
    vi.stubGlobal("fetch", f);

    const { pollProcessingStatus } = await import("../lib/tenders");
    const result = await pollProcessingStatus("t1", {
      intervalMs: 0,
      maxAttempts: 10,
    });
    expect(result.status).toBe("FAILED");
  });

  it("throws after maxAttempts if no terminal status", async () => {
    const responses = [
      {
        status: 200,
        body: {
          tenderId: "t1",
          status: "PROCESSING",
          progress: 10,
          processedChunks: 1,
          error: null,
        },
      },
    ];
    const f = mockFetch(responses);
    vi.stubGlobal("fetch", f);

    const { pollProcessingStatus } = await import("../lib/tenders");
    await expect(
      pollProcessingStatus("t1", { intervalMs: 0, maxAttempts: 2 }),
    ).rejects.toThrow();
  });
});

// ---------- tenderApi.remove ---------------------------------------------------
describe("tenderApi.remove", () => {
  it("sends DELETE /api/tenders/{id}/ and resolves on 204", async () => {
    const f = mockFetch([
      { status: 200, body: { csrfToken: "csrf1" } }, // CSRF
      { status: 204, body: null },
    ]);
    vi.stubGlobal("fetch", f);

    const { tenderApi } = await import("../lib/tenders");
    await expect(tenderApi.remove("t1")).resolves.toBeUndefined();

    const allCalls = f.mock.calls as unknown as Array<[string, RequestInit]>;
    const deleteCall = allCalls.find(
      ([, init]) => (init?.method ?? "").toUpperCase() === "DELETE",
    );
    expect(deleteCall).toBeTruthy();
    expect(deleteCall![0]).toBe("http://api.test/api/tenders/t1/");
  });

  it("propagates ApiClientError on 404 (cross-tenant ou inexistente)", async () => {
    const f = mockFetch([
      { status: 200, body: { csrfToken: "csrf1" } }, // CSRF
      {
        status: 404,
        body: {
          error: { code: "NOT_FOUND", message: "Não encontrado.", details: {} },
        },
      },
    ]);
    vi.stubGlobal("fetch", f);

    const { tenderApi } = await import("../lib/tenders");
    await expect(tenderApi.remove("t-other")).rejects.toMatchObject({
      statusCode: 404,
    });
  });
});
