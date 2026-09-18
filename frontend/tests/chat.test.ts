/**
 * Task 27 — Chat com citações
 * Testa: chatApi.send() com conversationId, mensagem, citações e erros.
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

describe("chatApi.send (Task 27)", () => {
  it("sends POST /api/tenders/{id}/chat/ with message and returns response with citations", async () => {
    const chatResponse = {
      conversationId: "conv-1",
      message: {
        id: "msg-1",
        role: "assistant",
        content: "Este edital prevê a contratação de serviços de TI.",
        citations: [
          {
            chunkId: "c1",
            pageNumber: 5,
            quote: "contratação de serviços de TI",
            score: 0.93,
          },
        ],
        createdAt: "2026-01-01T00:00:00Z",
      },
    };

    const f = mockFetch([
      { status: 200, body: { csrfToken: "csrf1" } },
      { status: 200, body: chatResponse },
    ]);
    vi.stubGlobal("fetch", f);

    const { chatApi } = await import("../lib/chat");
    const result = await chatApi.send({
      tenderId: "t1",
      message: "O que este edital prevê?",
    });

    expect(result.conversationId).toBe("conv-1");
    expect(result.message.role).toBe("assistant");
    expect(result.message.citations).toHaveLength(1);
    expect(result.message.citations[0].chunkId).toBe("c1");
  });

  it("includes conversationId in body when provided", async () => {
    const f = mockFetch([
      { status: 200, body: { csrfToken: "csrf1" } },
      {
        status: 200,
        body: {
          conversationId: "conv-2",
          message: {
            id: "msg-2",
            role: "assistant",
            content: "Resposta",
            citations: [],
            createdAt: "2026-01-01T00:00:00Z",
          },
        },
      },
    ]);
    vi.stubGlobal("fetch", f);

    const { chatApi } = await import("../lib/chat");
    await chatApi.send({
      tenderId: "t1",
      message: "Segunda mensagem",
      conversationId: "conv-2",
    });

    const allCalls = f.mock.calls as unknown as Array<[string, RequestInit]>;
    const chatCall = allCalls.find((c) => (c[0] as string).includes("/chat/"));
    expect(chatCall).toBeTruthy();
    if (chatCall) {
      const body = JSON.parse(chatCall[1].body as string);
      expect(body.conversationId).toBe("conv-2");
      expect(body.message).toBe("Segunda mensagem");
    }
  });

  it("uses a longer timeout for chat requests (RAG is synchronous)", async () => {
    const timeoutSpy = vi.spyOn(AbortSignal, "timeout");
    const f = mockFetch([
      { status: 200, body: { csrfToken: "csrf1" } },
      {
        status: 200,
        body: {
          conversationId: "conv-3",
          message: {
            id: "msg-3",
            role: "assistant",
            content: "Resposta",
            citations: [],
            createdAt: "2026-01-01T00:00:00Z",
          },
        },
      },
    ]);
    vi.stubGlobal("fetch", f);

    const { chatApi } = await import("../lib/chat");
    await chatApi.send({ tenderId: "t1", message: "Pergunta" });

    expect(timeoutSpy).toHaveBeenCalledWith(60000);
  });

  it("propagates 409 CONFLICT for unprocessed tender", async () => {
    const f = mockFetch([
      { status: 200, body: { csrfToken: "csrf1" } },
      {
        status: 409,
        body: {
          error: {
            code: "TENDER_NOT_PROCESSED",
            message: "Edital não está processado",
            details: {},
          },
        },
      },
    ]);
    vi.stubGlobal("fetch", f);

    const { chatApi } = await import("../lib/chat");
    await expect(
      chatApi.send({ tenderId: "t1", message: "msg" }),
    ).rejects.toMatchObject({ statusCode: 409, code: "TENDER_NOT_PROCESSED" });
  });

  it("propagates 429 RATE_LIMITED", async () => {
    const f = mockFetch([
      { status: 200, body: { csrfToken: "csrf1" } },
      {
        status: 429,
        body: {
          error: {
            code: "RATE_LIMITED",
            message: "Limite atingido",
            details: {},
          },
        },
      },
    ]);
    vi.stubGlobal("fetch", f);

    const { chatApi } = await import("../lib/chat");
    await expect(
      chatApi.send({ tenderId: "t1", message: "msg" }),
    ).rejects.toMatchObject({ statusCode: 429 });
  });

  it("returns empty citations array when no evidence found", async () => {
    const f = mockFetch([
      { status: 200, body: { csrfToken: "csrf1" } },
      {
        status: 200,
        body: {
          conversationId: "conv-3",
          message: {
            id: "msg-3",
            role: "assistant",
            content: "Não encontrei evidências suficientes para responder.",
            citations: [],
            createdAt: "2026-01-01T00:00:00Z",
          },
        },
      },
    ]);
    vi.stubGlobal("fetch", f);

    const { chatApi } = await import("../lib/chat");
    const result = await chatApi.send({
      tenderId: "t1",
      message: "xyz inexistente",
    });
    expect(result.message.citations).toHaveLength(0);
    expect(result.message.content).toContain("evidências");
  });
});
