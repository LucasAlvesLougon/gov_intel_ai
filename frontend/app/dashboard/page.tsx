"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { authStore, getCurrentCompany, getCurrentUser } from "../../lib/auth";
import {
  generateIdempotencyKey,
  pollProcessingStatus,
  tenderApi,
} from "../../lib/tenders";
import { ProcessingStatus, Tender } from "../../lib/types";
import Link from "next/link";

// --------------------------------------------------------------------------
// Tipos locais
// --------------------------------------------------------------------------
type UploadState =
  | { phase: "idle" }
  | { phase: "uploading" }
  | { phase: "polling"; tenderId: string; status: ProcessingStatus | null }
  | { phase: "done"; tenderId: string; status: ProcessingStatus }
  | { phase: "error"; message: string };

// --------------------------------------------------------------------------
// Componente principal
// --------------------------------------------------------------------------
export default function DashboardPage() {
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [loadingList, setLoadingList] = useState(false);
  const [listError, setListError] = useState<string | null>(null);

  const [uploadState, setUploadState] = useState<UploadState>({
    phase: "idle",
  });
  const fileInputRef = useRef<HTMLInputElement>(null);
  const titleRef = useRef<HTMLInputElement>(null);
  const descRef = useRef<HTMLTextAreaElement>(null);

  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const user = getCurrentUser();
  const company = getCurrentCompany();

  // --------------------------------------------------------------------------
  // Buscar lista de editais
  // --------------------------------------------------------------------------
  const fetchTenders = useCallback(async (p: number) => {
    setLoadingList(true);
    setListError(null);
    try {
      const res = await tenderApi.list({ page: p, pageSize: 20 });
      setTenders(res.data);
      setTotalPages(res.pagination.totalPages);
      setTotalItems(res.pagination.totalItems);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Erro ao carregar editais.";
      setListError(msg);
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => {
    fetchTenders(page);
  }, [fetchTenders, page]);

  // --------------------------------------------------------------------------
  // Upload de PDF
  // --------------------------------------------------------------------------
  const handleUpload = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const file = fileInputRef.current?.files?.[0];
    const title = titleRef.current?.value.trim() ?? "";
    const description = descRef.current?.value.trim() ?? "";

    if (!file) {
      setUploadState({ phase: "error", message: "Selecione um arquivo PDF." });
      return;
    }
    if (!title) {
      setUploadState({
        phase: "error",
        message: "Informe o título do edital.",
      });
      return;
    }

    const idempotencyKey = generateIdempotencyKey();
    setUploadState({ phase: "uploading" });

    try {
      const tender = await tenderApi.upload({
        file,
        title,
        description,
        idempotencyKey,
      });
      setUploadState({ phase: "polling", tenderId: tender.id, status: null });

      // Adicionar edital otimisticamente à lista
      setTenders((prev) => [tender, ...prev]);

      // Iniciar polling
      const finalStatus = await pollProcessingStatus(tender.id, {
        intervalMs: 2000,
        maxAttempts: 30,
        onUpdate: (s) => {
          setUploadState({ phase: "polling", tenderId: tender.id, status: s });
          // Atualizar status do edital na lista
          setTenders((prev) =>
            prev.map((t) =>
              t.id === tender.id ? { ...t, status: s.status } : t,
            ),
          );
        },
      });

      setUploadState({
        phase: "done",
        tenderId: tender.id,
        status: finalStatus,
      });
      // Atualizar estado final na lista
      setTenders((prev) =>
        prev.map((t) =>
          t.id === tender.id ? { ...t, status: finalStatus.status } : t,
        ),
      );

      // Reset do formulário
      if (fileInputRef.current) fileInputRef.current.value = "";
      if (titleRef.current) titleRef.current.value = "";
      if (descRef.current) descRef.current.value = "";
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Erro no upload. Tente novamente.";
      setUploadState({ phase: "error", message: msg });
    }
  };

  const handleLogout = async () => {
    try {
      await authStore.logout();
    } finally {
      window.location.href = "/login";
    }
  };

  // --------------------------------------------------------------------------
  // Exclusão de edital
  // --------------------------------------------------------------------------
  const handleDelete = async (tenderId: string) => {
    if (
      !window.confirm(
        "Excluir este edital? O arquivo, o processamento e as conversas serão apagados.",
      )
    ) {
      return;
    }
    setDeletingId(tenderId);
    setDeleteError(null);
    try {
      await tenderApi.remove(tenderId);
      setTenders((prev) => prev.filter((t) => t.id !== tenderId));
      setTotalItems((n) => Math.max(0, n - 1));
      // Recarrega a lista para manter a paginação consistente
      await fetchTenders(page);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Erro ao excluir o edital.";
      setDeleteError(msg);
    } finally {
      setDeletingId(null);
    }
  };

  // --------------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------------
  return (
    <div className="dashboard-container">
      {/* Cabeçalho */}
      <header className="dashboard-header">
        <div className="dashboard-header-content">
          <h1>GovIntel AI</h1>
          <div className="dashboard-user-info">
            <span id="dashboard-company-name">{company?.name ?? ""}</span>
            <span>{user?.email ?? ""}</span>
            <button
              id="dashboard-logout-btn"
              className="btn-secondary"
              onClick={handleLogout}
            >
              Sair
            </button>
          </div>
        </div>
      </header>

      <main className="dashboard-main">
        {/* Upload */}
        <section
          className="dashboard-upload-section"
          aria-labelledby="upload-heading"
        >
          <h2 id="upload-heading">Enviar Edital</h2>
          <form
            id="upload-form"
            onSubmit={handleUpload}
            className="upload-form"
            noValidate
          >
            <div className="form-group">
              <label htmlFor="upload-title">Título *</label>
              <input
                id="upload-title"
                type="text"
                ref={titleRef}
                placeholder="Ex: Pregão Eletrônico 001/2026"
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="upload-description">Descrição</label>
              <textarea
                id="upload-description"
                ref={descRef}
                rows={2}
                placeholder="Descrição opcional"
              />
            </div>
            <div className="form-group">
              <label htmlFor="upload-file">Arquivo PDF *</label>
              <input
                id="upload-file"
                type="file"
                accept="application/pdf"
                ref={fileInputRef}
                required
              />
            </div>

            <button
              id="upload-submit-btn"
              type="submit"
              className="btn-primary"
              disabled={
                uploadState.phase === "uploading" ||
                uploadState.phase === "polling"
              }
            >
              {uploadState.phase === "uploading"
                ? "Enviando…"
                : uploadState.phase === "polling"
                  ? "Processando…"
                  : "Enviar PDF"}
            </button>
          </form>

          {/* Status de upload/polling */}
          {uploadState.phase === "polling" && uploadState.status && (
            <div
              id="upload-status-polling"
              className="upload-status upload-status--processing"
              role="status"
              aria-live="polite"
            >
              Processando: {uploadState.status.progress}% (
              {uploadState.status.processedChunks} chunks)
            </div>
          )}
          {uploadState.phase === "done" && (
            <div
              id="upload-status-done"
              className={`upload-status ${
                uploadState.status.status === "PROCESSED"
                  ? "upload-status--success"
                  : "upload-status--error"
              }`}
              role="status"
              aria-live="polite"
            >
              {uploadState.status.status === "PROCESSED"
                ? "✓ Edital processado com sucesso."
                : `✗ Falha no processamento.${
                    uploadState.status.error
                      ? " " + uploadState.status.error.message
                      : ""
                  }`}
            </div>
          )}
          {uploadState.phase === "error" && (
            <div
              id="upload-status-error"
              className="upload-status upload-status--error alert-error"
              role="alert"
            >
              {uploadState.message}
            </div>
          )}
        </section>

        {/* Lista de editais */}
        <section
          className="dashboard-tenders-section"
          aria-labelledby="tenders-heading"
        >
          <div className="tenders-header">
            <h2 id="tenders-heading">Editais</h2>
            <span className="tenders-count">{totalItems} edital(is)</span>
          </div>

          {listError && (
            <div className="alert-error" role="alert">
              {listError}
            </div>
          )}

          {deleteError && (
            <div className="alert-error" role="alert">
              {deleteError}
            </div>
          )}

          {loadingList ? (
            <p id="tenders-loading" role="status">
              Carregando…
            </p>
          ) : tenders.length === 0 ? (
            <p id="tenders-empty">Nenhum edital enviado ainda.</p>
          ) : (
            <ul id="tenders-list" className="tenders-list">
              {tenders.map((t) => (
                <li key={t.id} className="tender-item">
                  <div className="tender-item-header">
                    <span className="tender-title">{t.title}</span>
                    <span
                      className={`tender-status tender-status--${t.status.toLowerCase()}`}
                    >
                      {t.status}
                    </span>
                  </div>
                  {t.description && (
                    <p className="tender-description">{t.description}</p>
                  )}
                  <div className="tender-actions">
                    {t.status === "PROCESSED" && (
                      <>
                        <Link
                          href={`/search?tenderId=${t.id}`}
                          className="btn-link"
                        >
                          Buscar
                        </Link>
                        <Link
                          href={`/chat?tenderId=${t.id}`}
                          className="btn-link"
                        >
                          Chat
                        </Link>
                      </>
                    )}
                    <button
                      type="button"
                      className="btn-danger"
                      onClick={() => handleDelete(t.id)}
                      disabled={deletingId === t.id}
                    >
                      {deletingId === t.id ? "Excluindo…" : "Excluir"}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}

          {/* Paginação */}
          {totalPages > 1 && (
            <nav className="pagination" aria-label="Paginação de editais">
              <button
                id="pagination-prev"
                className="btn-secondary"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                ← Anterior
              </button>
              <span>
                Página {page} de {totalPages}
              </span>
              <button
                id="pagination-next"
                className="btn-secondary"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
              >
                Próxima →
              </button>
            </nav>
          )}
        </section>
      </main>
    </div>
  );
}
