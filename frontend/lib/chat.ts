/**
 * chat.ts — API client para o chat RAG
 *
 * POST /api/tenders/{id}/chat/ com message e conversationId opcional.
 * Retorna resposta do LLM com citações verificáveis.
 */
import { apiRequest } from "./http";
import { ChatResponse } from "./types";

// --------------------------------------------------------------------------
// Tipos
// --------------------------------------------------------------------------

export interface ChatSendParams {
  tenderId: string;
  message: string;
  conversationId?: string;
}

// --------------------------------------------------------------------------
// API de chat
// --------------------------------------------------------------------------

export const chatApi = {
  /**
   * POST /api/tenders/{id}/chat/ — envia mensagem e obtém resposta RAG com citações.
   * conversationId incluído apenas se fornecido (continua conversa existente).
   * 409 → edital não processado; 429 → throttle; 404 → edital não encontrado.
   */
  async send(params: ChatSendParams): Promise<ChatResponse> {
    const body: Record<string, unknown> = { message: params.message };
    if (params.conversationId != null) {
      body.conversationId = params.conversationId;
    }

    return apiRequest<ChatResponse>(
      `/api/tenders/${encodeURIComponent(params.tenderId)}/chat/`,
      {
        method: "POST",
        body: JSON.stringify(body),
        // RAG é síncrono (embeddings + LLM); dá folga maior que o default 15s.
        timeoutMs: 60000,
      },
    );
  },
};
