import { afterEach, expect, it, vi } from "vitest";
import { getApiBaseUrl } from "../lib/api-url";
import { apiRequest } from "../lib/http";

afterEach(() => vi.unstubAllGlobals());

it("alinha hosts locais para manter cookies no mesmo site", () => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://localhost:8000";
  vi.stubGlobal("window", {
    location: { href: "http://127.0.0.1:3000/register" },
  });
  expect(getApiBaseUrl()).toBe("http://127.0.0.1:8000");
});

it("uses the configured API origin", async () => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://localhost:8000";
  const fetcher = vi.fn().mockResolvedValue(Response.json({ status: "ok" }));
  vi.stubGlobal("fetch", fetcher);
  await expect(apiRequest("/health/")).resolves.toEqual({ status: "ok" });
  expect(fetcher.mock.calls[0][0]).toBe("http://localhost:8000/health/");
});

it("does not send requests to a caller-controlled origin", async () => {
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  await expect(apiRequest("//attacker.invalid/")).rejects.toThrow();
  expect(fetcher).not.toHaveBeenCalled();
});

it("never exposes upstream HTML on failure", async () => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://localhost:8000";
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(new Response("private traceback", { status: 500 })),
  );
  await expect(apiRequest("/health/")).rejects.toThrow(
    "Não foi possível concluir a solicitação.",
  );
});
