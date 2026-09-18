/**
 * Task 26 — Busca Semântica
 * Testa: searchApi.search() com parâmetros, paginação, loading/vazio/erro.
 *
 * Padrão: sem JSX; mocks de fetch globais.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

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
  vi.resetModules();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

// ---------- searchApi.search ---------------------------------------------------
describe("searchApi.search (Task 26)", () => {
  it("sends POST /api/search/semantic/ with query and returns paginated results", async () => {
    const csrfMock = { status: 200, body: { csrfToken: "csrf1" } };
    const resultMock = {
      status: 200,
      body: {
        data: [
          {
            chunkId: "c1",
            tenderId: "t1",
            pageNumber: 3,
            startCharOffset: 100,
            endCharOffset: 300,
            snippet: "texto relevante aqui",
            score: 0.91,
          },
        ],
        pagination: { page: 1, pageSize: 20, totalItems: 1, totalPages: 1 },
      },
    };
    const f = mockFetch([csrfMock, resultMock]);
    vi.stubGlobal("fetch", f);

    const { searchApi } = await import("../lib/search");
    const result = await searchApi.search({ query: "licitação pública" });

    expect(result.data).toHaveLength(1);
    expect(result.data[0].chunkId).toBe("c1");
    expect(result.data[0].score).toBe(0.91);
    expect(result.pagination.totalItems).toBe(1);
  });

  it("includes optional tenderId, topK, page, pageSize in request body", async () => {
    const f = mockFetch([
      { status: 200, body: { csrfToken: "csrf1" } },
      {
        status: 200,
        body: {
          data: [],
          pagination: { page: 2, pageSize: 5, totalItems: 0, totalPages: 0 },
        },
      },
    ]);
    vi.stubGlobal("fetch", f);

    const { searchApi } = await import("../lib/search");
    await searchApi.search({
      query: "pregão",
      tenderId: "t1",
      topK: 8,
      page: 2,
      pageSize: 5,
    });

    // Verifica o body da requisição de busca (segunda chamada = após CSRF)
    const allCalls = f.mock.calls as unknown as Array<[string, RequestInit]>;
    const searchCall = allCalls.find((c) =>
      (c[0] as string).includes("/api/search/semantic/"),
    );
    expect(searchCall).toBeTruthy();
    if (searchCall) {
      const body = JSON.parse(searchCall[1].body as string);
      expect(body.query).toBe("pregão");
      expect(body.tenderId).toBe("t1");
      expect(body.topK).toBe(8);
      expect(body.page).toBe(2);
      expect(body.pageSize).toBe(5);
    }
  });

  it("returns empty data array on empty results", async () => {
    const f = mockFetch([
      { status: 200, body: { csrfToken: "csrf1" } },
      {
        status: 200,
        body: {
          data: [],
          pagination: { page: 1, pageSize: 20, totalItems: 0, totalPages: 0 },
        },
      },
    ]);
    vi.stubGlobal("fetch", f);

    const { searchApi } = await import("../lib/search");
    const result = await searchApi.search({ query: "xyz inexistente" });
    expect(result.data).toHaveLength(0);
    expect(result.pagination.totalItems).toBe(0);
  });

  it("propagates ApiClientError on non-200 response", async () => {
    const f = mockFetch([
      { status: 200, body: { csrfToken: "csrf1" } },
      {
        status: 400,
        body: {
          error: {
            code: "VALIDATION_ERROR",
            message: "query é obrigatória",
            details: {},
          },
        },
      },
    ]);
    vi.stubGlobal("fetch", f);

    const { searchApi } = await import("../lib/search");
    await expect(searchApi.search({ query: "" })).rejects.toMatchObject({
      statusCode: 400,
      code: "VALIDATION_ERROR",
    });
  });

  it("propagates ApiClientError on 429 rate limit", async () => {
    const f = mockFetch([
      { status: 200, body: { csrfToken: "csrf1" } },
      {
        status: 429,
        body: {
          error: {
            code: "RATE_LIMITED",
            message: "Muitas requisições",
            details: {},
          },
        },
      },
    ]);
    vi.stubGlobal("fetch", f);

    const { searchApi } = await import("../lib/search");
    await expect(searchApi.search({ query: "qualquer" })).rejects.toMatchObject(
      { statusCode: 429 },
    );
  });

  it("omits undefined optional fields from request body", async () => {
    const f = mockFetch([
      { status: 200, body: { csrfToken: "csrf1" } },
      {
        status: 200,
        body: {
          data: [],
          pagination: { page: 1, pageSize: 20, totalItems: 0, totalPages: 0 },
        },
      },
    ]);
    vi.stubGlobal("fetch", f);

    const { searchApi } = await import("../lib/search");
    await searchApi.search({ query: "test" });

    const allCalls = f.mock.calls as unknown as Array<[string, RequestInit]>;
    const searchCall = allCalls.find((c) =>
      (c[0] as string).includes("/api/search/semantic/"),
    );
    expect(searchCall).toBeTruthy();
    if (searchCall) {
      const body = JSON.parse(searchCall[1].body as string);
      // tenderId, topK, page, pageSize não devem aparecer quando não fornecidos
      expect(body).not.toHaveProperty("tenderId");
      expect(body).not.toHaveProperty("topK");
    }
  });
});
