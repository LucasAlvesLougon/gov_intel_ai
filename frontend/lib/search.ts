/**
 * search.ts — API client para busca semântica
 *
 * POST /api/search/semantic/ com query, tenderId opcional, topK, page e pageSize.
 * Nunca acessa localStorage; usa apiRequest com Bearer + CSRF injetados automaticamente.
 */
import { apiRequest } from "./http";
import { PaginatedResponse, SearchResultItem } from "./types";

// --------------------------------------------------------------------------
// Tipos
// --------------------------------------------------------------------------

export interface SearchParams {
  query: string;
  tenderId?: string;
  topK?: number;
  page?: number;
  pageSize?: number;
}

export type SearchResults = PaginatedResponse<SearchResultItem>;

// --------------------------------------------------------------------------
// API de busca semântica
// --------------------------------------------------------------------------

export const searchApi = {
  /**
   * POST /api/search/semantic/ — busca vetorial por similaridade.
   * Campos opcionais ausentes NÃO são incluídos no body para evitar validação
   * desnecessária no backend.
   */
  async search(params: SearchParams): Promise<SearchResults> {
    const body: Record<string, unknown> = { query: params.query };
    if (params.tenderId != null) body.tenderId = params.tenderId;
    if (params.topK != null) body.topK = params.topK;
    if (params.page != null) body.page = params.page;
    if (params.pageSize != null) body.pageSize = params.pageSize;

    return apiRequest<SearchResults>("/api/search/semantic/", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
};
