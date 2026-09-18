/**
 * tenders.ts — API client para editais (Tenders)
 *
 * Expõe tenderApi (list, upload, getStatus) e utilitários de polling.
 * Nunca acessa localStorage; usa apiRequest que injeta Bearer + CSRF automaticamente.
 */
import { apiRequest } from "./http";
import { PaginatedResponse, ProcessingStatus, Tender } from "./types";

// --------------------------------------------------------------------------
// Tipos internos
// --------------------------------------------------------------------------

export interface TenderListParams {
  page?: number;
  pageSize?: number;
  status?: string;
  sortBy?: string;
  sortOrder?: "asc" | "desc";
}

export interface UploadParams {
  file: File;
  title: string;
  description: string;
  idempotencyKey: string;
}

export interface PollOptions {
  /** Intervalo entre tentativas em ms (default: 2000) */
  intervalMs?: number;
  /** Máximo de tentativas antes de lançar erro (default: 30) */
  maxAttempts?: number;
  /** Callback opcional chamado a cada atualização de status */
  onUpdate?: (status: ProcessingStatus) => void;
}

// --------------------------------------------------------------------------
// Gerador de Idempotency-Key
// --------------------------------------------------------------------------

/**
 * Gera uma chave de idempotência única por upload.
 * Usa crypto.randomUUID quando disponível, com fallback para Math.random.
 */
export function generateIdempotencyKey(): string {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  // Fallback para ambientes onde crypto.randomUUID não existe (ex: vitest JSDOM)
  return (
    Date.now().toString(36) +
    "-" +
    Math.random().toString(36).slice(2, 10) +
    "-" +
    Math.random().toString(36).slice(2, 10)
  );
}

// --------------------------------------------------------------------------
// API de editais
// --------------------------------------------------------------------------

export const tenderApi = {
  /**
   * GET /api/tenders/ — lista paginada de editais do tenant autenticado.
   */
  async list(
    params: TenderListParams = {},
  ): Promise<PaginatedResponse<Tender>> {
    const qs = new URLSearchParams();
    if (params.page != null) qs.set("page", String(params.page));
    if (params.pageSize != null) qs.set("pageSize", String(params.pageSize));
    if (params.status) qs.set("status", params.status);
    if (params.sortBy) qs.set("sortBy", params.sortBy);
    if (params.sortOrder) qs.set("sortOrder", params.sortOrder);

    const query = qs.toString();
    const path = query ? `/api/tenders/?${query}` : "/api/tenders/";
    return apiRequest<PaginatedResponse<Tender>>(path, { method: "GET" });
  },

  /**
   * POST /api/tenders/ — upload multipart de PDF com chave de idempotência.
   * O Content-Type não é definido manualmente para permitir que o browser/fetch
   * defina o boundary correto do multipart automaticamente.
   */
  async upload(params: UploadParams): Promise<Tender> {
    const form = new FormData();
    form.append("file", params.file, params.file.name);
    form.append("title", params.title);
    form.append("description", params.description);

    // apiRequest injeta CSRF e Bearer, mas não define Content-Type em FormData
    // para preservar o boundary multipart. Passamos os headers customizados aqui.
    return apiRequest<Tender>("/api/tenders/", {
      method: "POST",
      body: form,
      headers: {
        "Idempotency-Key": params.idempotencyKey,
      },
    });
  },

  /**
   * GET /api/tenders/{id}/processing-status/ — status atual do processamento.
   */
  async getStatus(tenderId: string): Promise<ProcessingStatus> {
    return apiRequest<ProcessingStatus>(
      `/api/tenders/${encodeURIComponent(tenderId)}/processing-status/`,
      { method: "GET" },
    );
  },

  /**
   * DELETE /api/tenders/{id}/ — remove o edital, o blob privado, os chunks,
   * as conversas e invalida o cache do tenant (contrato: 204 No Content).
   */
  async remove(tenderId: string): Promise<void> {
    await apiRequest<void>(`/api/tenders/${encodeURIComponent(tenderId)}/`, {
      method: "DELETE",
    });
  },
};

// --------------------------------------------------------------------------
// Polling de status de processamento
// --------------------------------------------------------------------------

const TERMINAL_STATUSES = new Set(["PROCESSED", "FAILED"]);

/**
 * Faz polling de GET /api/tenders/{id}/processing-status/ até encontrar
 * um status terminal (PROCESSED ou FAILED) ou esgotar maxAttempts.
 *
 * Conforme contrato: primeira chamada após 1s (ou intervalMs), depois cada
 * intervalMs ms. Por padrão intervalMs=2000 e maxAttempts=30.
 */
export async function pollProcessingStatus(
  tenderId: string,
  options: PollOptions = {},
): Promise<ProcessingStatus> {
  const { intervalMs = 2000, maxAttempts = 30, onUpdate } = options;

  const sleep = (ms: number) =>
    new Promise<void>((resolve) => setTimeout(resolve, ms));

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    if (attempt > 0) {
      await sleep(intervalMs);
    }

    const status = await tenderApi.getStatus(tenderId);
    onUpdate?.(status);

    if (TERMINAL_STATUSES.has(status.status)) {
      return status;
    }
  }

  throw new Error(
    `Polling esgotado após ${maxAttempts} tentativas para o edital ${tenderId}.`,
  );
}
