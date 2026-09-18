// @vitest-environment jsdom
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import React from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

const { sendMock } = vi.hoisted(() => ({ sendMock: vi.fn() }));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("tenderId=t-1"),
}));

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) =>
    React.createElement("a", { href }, children),
}));

vi.mock("../lib/chat", () => ({
  chatApi: { send: sendMock },
}));

describe("Chat citation toggle", () => {
  afterEach(() => {
    cleanup();
    sendMock.mockReset();
  });

  it("expands and collapses citations inline when clicking the toggle button", async () => {
    sendMock.mockResolvedValue({
      conversationId: "c-1",
      message: {
        id: "m-1",
        role: "assistant",
        content: "O prazo é de 45 dias.",
        citations: [
          {
            chunkId: "chunk-1",
            pageNumber: 3,
            quote: "O prazo de entrega será de 45 dias corridos.",
            score: 0.87,
          },
        ],
      },
    });

    const { ChatView } = await import("../components/chat-view");
    render(<ChatView />);

    const input = screen.getByLabelText("Mensagem") as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: "Qual o prazo de entrega?" } });
    const form = document.querySelector("#chat-form") as HTMLFormElement;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByText("O prazo é de 45 dias.")).toBeTruthy();
    });

    const toggle = screen.getByRole("button", {
      name: /1 citação\(ões\) — ver fontes/,
    });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    // Antes de expandir não há lista inline (a citação pode estar no painel lateral)
    expect(screen.queryByLabelText("Citações desta mensagem")).toBeNull();

    fireEvent.click(toggle);

    const expandedToggle = screen.getByRole("button", {
      name: /1 citação\(ões\) — ocultar fontes/,
    });
    expect(expandedToggle.getAttribute("aria-expanded")).toBe("true");
    const inlineList = screen.getByLabelText("Citações desta mensagem");
    expect(inlineList.textContent).toContain(
      "O prazo de entrega será de 45 dias corridos",
    );
    expect(inlineList.textContent).toContain("Página 3");

    fireEvent.click(expandedToggle);

    expect(
      screen
        .getByRole("button", { name: /1 citação\(ões\) — ver fontes/ })
        .getAttribute("aria-expanded"),
    ).toBe("false");
    // Lista inline recolhida; a citação permanece no painel lateral "Fontes"
    expect(screen.queryByLabelText("Citações desta mensagem")).toBeNull();
    expect(
      screen.getByText(/O prazo de entrega será de 45 dias corridos/),
    ).toBeTruthy();
  });

  it("shows a friendly message when the request times out", async () => {
    sendMock.mockRejectedValue(
      new DOMException("The operation timed out.", "TimeoutError"),
    );

    const { ChatView } = await import("../components/chat-view");
    render(<ChatView />);

    const input = screen.getByLabelText("Mensagem") as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: "Qual o prazo?" } });
    const form = document.querySelector("#chat-form") as HTMLFormElement;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByText(/O modelo demorou para responder/)).toBeTruthy();
    });
  });
});
