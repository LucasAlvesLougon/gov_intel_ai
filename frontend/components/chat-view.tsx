"use client";

import { useEffect, useRef, useState } from "react";
import { chatApi } from "../lib/chat";
import { ApiClientError } from "../lib/http";
import { Citation } from "../lib/types";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

// --------------------------------------------------------------------------
// Tipos locais
// --------------------------------------------------------------------------
interface ChatEntry {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
}

// --------------------------------------------------------------------------
// Componente principal
// --------------------------------------------------------------------------
export function ChatView() {
  const searchParams = useSearchParams();
  const tenderId = searchParams.get("tenderId") ?? "";

  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeCitations, setActiveCitations] = useState<Citation[]>([]);
  const [expandedMessageId, setExpandedMessageId] = useState<string | null>(
    null,
  );

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Rolar para o final quando chegam novas mensagens
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (!tenderId) {
    return (
      <div className="chat-page">
        <header className="dashboard-header">
          <div className="dashboard-header-content">
            <h1>GovIntel AI — Chat</h1>
            <Link href="/dashboard" className="btn-link">
              ← Dashboard
            </Link>
          </div>
        </header>
        <main className="search-main">
          <div className="alert-error" role="alert">
            Nenhum edital selecionado.{" "}
            <Link href="/dashboard" className="btn-link">
              Ir para o Dashboard
            </Link>
          </div>
        </main>
      </div>
    );
  }

  // --------------------------------------------------------------------------
  // Enviar mensagem
  // --------------------------------------------------------------------------
  const handleSend = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;

    const userEntry: ChatEntry = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
      citations: [],
    };
    setMessages((prev) => [...prev, userEntry]);
    setInput("");
    setError(null);
    setSending(true);

    try {
      const res = await chatApi.send({
        tenderId,
        message: text,
        ...(conversationId ? { conversationId } : {}),
      });

      setConversationId(res.conversationId);

      const assistantEntry: ChatEntry = {
        id: res.message.id,
        role: "assistant",
        content: res.message.content,
        citations: res.message.citations,
      };
      setMessages((prev) => [...prev, assistantEntry]);
      // Mostrar citações da última resposta no painel lateral
      setActiveCitations(res.message.citations);
    } catch (err: unknown) {
      let msg = "Erro ao enviar mensagem.";
      if (err instanceof ApiClientError) {
        if (err.statusCode === 409) {
          msg = "Este edital ainda não foi processado. Tente mais tarde.";
        } else if (err.statusCode === 429) {
          msg = "Muitas requisições. Aguarde um momento e tente novamente.";
        } else {
          msg = err.message;
        }
      } else if (isTimeoutError(err)) {
        msg =
          "O modelo demorou para responder. Aguarde um momento e tente novamente.";
      } else if (err instanceof Error) {
        msg = err.message;
      }
      setError(msg);
      // Remove a mensagem do usuário se houve erro (evita mensagem órfã)
      setMessages((prev) => prev.filter((m) => m.id !== userEntry.id));
      setInput(text);
    } finally {
      setSending(false);
    }
  };

  // --------------------------------------------------------------------------
  // Erros de rede/abort
  // --------------------------------------------------------------------------
  function isTimeoutError(err: unknown): boolean {
    if (err instanceof Error) {
      return err.name === "TimeoutError" || err.message.includes("timed out");
    }
    if (err && typeof err === "object") {
      const e = err as { name?: unknown; message?: unknown };
      return (
        e.name === "TimeoutError" ||
        String(e.message ?? "").includes("timed out")
      );
    }
    return false;
  }

  // --------------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------------
  return (
    <div className="chat-page">
      {/* Cabeçalho */}
      <header className="dashboard-header">
        <div className="dashboard-header-content">
          <h1>GovIntel AI — Chat</h1>
          <nav className="nav-links">
            <Link href={`/search?tenderId=${tenderId}`} className="btn-link">
              ← Busca
            </Link>
            <Link href="/dashboard" className="btn-link">
              Dashboard
            </Link>
          </nav>
        </div>
      </header>

      <main className="chat-main">
        {/* Coluna principal: mensagens */}
        <section className="chat-section" aria-labelledby="chat-heading">
          <h2 id="chat-heading" className="sr-only">
            Conversa sobre o edital
          </h2>

          {/* Lista de mensagens */}
          <div
            id="chat-messages"
            className="chat-messages"
            role="log"
            aria-live="polite"
            aria-label="Mensagens do chat"
          >
            {messages.length === 0 && (
              <p
                id="chat-empty"
                className="search-status"
                style={{ margin: "auto", textAlign: "center" }}
              >
                Faça uma pergunta sobre o edital.
              </p>
            )}
            {messages.map((msg) => {
              const isExpanded = expandedMessageId === msg.id;
              return (
                <div
                  key={msg.id}
                  className={`chat-message chat-message--${msg.role}`}
                >
                  <div className="chat-message-role">
                    {msg.role === "user" ? "Você" : "GovIntel AI"}
                  </div>
                  {msg.content}
                  {msg.citations.length > 0 && (
                    <>
                      <button
                        type="button"
                        className="chat-citations-toggle"
                        aria-expanded={isExpanded}
                        onClick={() => {
                          if (isExpanded) {
                            setExpandedMessageId(null);
                          } else {
                            setExpandedMessageId(msg.id);
                            setActiveCitations(msg.citations);
                          }
                        }}
                      >
                        {msg.citations.length} citação(ões) —{" "}
                        {isExpanded ? "ocultar" : "ver"} fontes
                      </button>
                      {isExpanded && (
                        <ul
                          className="chat-citations-list chat-citations-inline"
                          aria-label="Citações desta mensagem"
                        >
                          {msg.citations.map((c) => (
                            <li key={c.chunkId} className="chat-citation-item">
                              <div className="chat-citation-page">
                                Página {c.pageNumber}
                                {c.score != null && (
                                  <span
                                    style={{
                                      fontWeight: 400,
                                      marginLeft: "0.5rem",
                                    }}
                                  >
                                    ({(c.score * 100).toFixed(0)}%)
                                  </span>
                                )}
                              </div>
                              <p className="chat-citation-quote">
                                &ldquo;{c.quote}&rdquo;
                              </p>
                            </li>
                          ))}
                        </ul>
                      )}
                    </>
                  )}
                </div>
              );
            })}
            <div ref={messagesEndRef} />
          </div>

          {/* Erro */}
          {error && (
            <div
              id="chat-error"
              className="upload-status upload-status--error"
              role="alert"
              style={{ margin: "0.5rem 0.75rem" }}
            >
              {error}
            </div>
          )}

          {/* Formulário de entrada */}
          <form
            id="chat-form"
            onSubmit={handleSend}
            className="chat-input-form"
          >
            <label htmlFor="chat-input" className="sr-only">
              Mensagem
            </label>
            <textarea
              id="chat-input"
              className="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  e.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder="Faça uma pergunta sobre o edital… (Enter para enviar)"
              rows={2}
              disabled={sending}
            />
            <button
              id="chat-send-btn"
              type="submit"
              className="btn-primary"
              disabled={sending || !input.trim()}
            >
              {sending ? "…" : "Enviar"}
            </button>
          </form>
        </section>

        {/* Painel lateral: citações */}
        <aside
          className="chat-citations-section"
          aria-labelledby="citations-heading"
        >
          <h3 id="citations-heading">Fontes</h3>
          {activeCitations.length === 0 ? (
            <p
              id="citations-empty"
              className="search-status"
              style={{ fontSize: "0.8rem" }}
            >
              As citações da resposta aparecerão aqui.
            </p>
          ) : (
            <ul
              id="citations-list"
              className="chat-citations-list"
              aria-label="Citações da resposta"
            >
              {activeCitations.map((c) => (
                <li key={c.chunkId} className="chat-citation-item">
                  <div className="chat-citation-page">
                    Página {c.pageNumber}
                    {c.score != null && (
                      <span style={{ fontWeight: 400, marginLeft: "0.5rem" }}>
                        ({(c.score * 100).toFixed(0)}%)
                      </span>
                    )}
                  </div>
                  <p className="chat-citation-quote">&ldquo;{c.quote}&rdquo;</p>
                </li>
              ))}
            </ul>
          )}
        </aside>
      </main>
    </div>
  );
}
