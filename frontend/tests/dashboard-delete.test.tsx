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

const { removeMock, listMock } = vi.hoisted(() => ({
  removeMock: vi.fn(),
  listMock: vi.fn(),
}));

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) =>
    React.createElement("a", { href }, children),
}));

vi.mock("../lib/auth", () => ({
  authStore: { logout: vi.fn() },
  getCurrentUser: () => ({ email: "user@test.com" }),
  getCurrentCompany: () => ({ name: "Empresa Teste" }),
}));

vi.mock("../lib/tenders", () => ({
  tenderApi: { list: listMock, remove: removeMock },
  generateIdempotencyKey: vi.fn(() => "idem-key"),
  pollProcessingStatus: vi.fn(),
}));

const TENDER_FIXTURE = {
  id: "t-1",
  title: "Edital para excluir",
  description: "",
  status: "PENDING",
  fileSize: 1024,
  originalFilename: "edital.pdf",
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

const PAGE_FIXTURE = {
  data: [TENDER_FIXTURE],
  pagination: { page: 1, pageSize: 20, totalItems: 1, totalPages: 1 },
};

describe("Dashboard delete tender", () => {
  afterEach(() => {
    cleanup();
    removeMock.mockReset();
    listMock.mockReset();
  });

  it("exclui o edital com confirmação e remove da lista", async () => {
    listMock.mockResolvedValueOnce(PAGE_FIXTURE).mockResolvedValueOnce({
      data: [],
      pagination: { page: 1, pageSize: 20, totalItems: 0, totalPages: 1 },
    });
    removeMock.mockResolvedValue(undefined);
    window.confirm = vi.fn(() => true);

    const { default: DashboardPage } = await import("../app/dashboard/page");
    render(<DashboardPage />);

    await screen.findByText("Edital para excluir");
    expect(listMock).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: /Excluir/ }));

    await waitFor(() => {
      expect(removeMock).toHaveBeenCalledWith("t-1");
    });
    expect(window.confirm).toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.queryByText("Edital para excluir")).toBeNull();
    });
    // Lista é recarregada após a exclusão
    expect(listMock).toHaveBeenCalledTimes(2);
  });

  it("não exclui quando o usuário cancela a confirmação", async () => {
    listMock.mockResolvedValue(PAGE_FIXTURE);
    window.confirm = vi.fn(() => false);

    const { default: DashboardPage } = await import("../app/dashboard/page");
    render(<DashboardPage />);

    await screen.findByText("Edital para excluir");
    fireEvent.click(screen.getByRole("button", { name: /Excluir/ }));

    expect(removeMock).not.toHaveBeenCalled();
    expect(screen.getByText("Edital para excluir")).toBeTruthy();
  });

  it("exibe erro quando a exclusão falha e mantém o edital", async () => {
    listMock.mockResolvedValue(PAGE_FIXTURE);
    removeMock.mockRejectedValue(
      Object.assign(new Error("Não encontrado."), { statusCode: 404 }),
    );
    window.confirm = vi.fn(() => true);

    const { default: DashboardPage } = await import("../app/dashboard/page");
    render(<DashboardPage />);

    await screen.findByText("Edital para excluir");
    fireEvent.click(screen.getByRole("button", { name: /Excluir/ }));

    await waitFor(() => {
      expect(screen.getByText(/Erro ao excluir|Não encontrado\./)).toBeTruthy();
    });
    expect(screen.getByText("Edital para excluir")).toBeTruthy();
  });
});
