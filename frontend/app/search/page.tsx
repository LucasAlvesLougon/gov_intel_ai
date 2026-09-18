"use client";

import { useCallback, useEffect, useState } from "react";
import { searchApi } from "../../lib/search";
import { tenderApi } from "../../lib/tenders";
import { SearchResultItem, Tender } from "../../lib/types";
import Link from "next/link";

// --------------------------------------------------------------------------
// Tipos locais
// --------------------------------------------------------------------------
interface SearchState {
  phase: "idle" | "loading" | "done" | "error";
  results: SearchResultItem[];
  totalItems: number;
  totalPages: number;
  currentPage: number;
  error: string | null;
}

// --------------------------------------------------------------------------
// Componente principal
// --------------------------------------------------------------------------
export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [selectedTenderId, setSelectedTenderId] = useState<string>("");
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [loadingTenders, setLoadingTenders] = useState(false);
  const [state, setState] = useState<SearchState>({
    phase: "idle",
    results: [],
    totalItems: 0,
    totalPages: 1,
    currentPage: 1,
    error: null,
  });

  // Pré-carregar lista de editais PROCESSED para o filtro
  useEffect(() => {
    setLoadingTenders(true);
    tenderApi
      .list({ status: "PROCESSED", pageSize: 50 })
      .then((r) => setTenders(r.data))
      .catch(() => setTenders([]))
      .finally(() => setLoadingTenders(false));
  }, []);

  // --------------------------------------------------------------------------
  // Busca
  // --------------------------------------------------------------------------
  const doSearch = useCallback(
    async (q: string, tenderId: string, page: number) => {
      if (!q.trim()) return;
      setState((prev) => ({
        ...prev,
        phase: "loading",
        error: null,
        currentPage: page,
      }));
      try {
        const res = await searchApi.search({
          query: q.trim(),
          ...(tenderId ? { tenderId } : {}),
          page,
          pageSize: 10,
          topK: 8,
        });
        setState({
          phase: "done",
          results: res.data,
          totalItems: res.pagination.totalItems,
          totalPages: res.pagination.totalPages,
          currentPage: res.pagination.page,
          error: null,
        });
      } catch (err: unknown) {
        const msg =
          err instanceof Error
            ? err.message
            : "Erro na busca. Tente novamente.";
        setState((prev) => ({
          ...prev,
          phase: "error",
          results: [],
          error: msg,
        }));
      }
    },
    [],
  );

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    doSearch(query, selectedTenderId, 1);
  };

  const handlePageChange = (p: number) => {
    doSearch(query, selectedTenderId, p);
  };

  // --------------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------------
  return (
    <div className="search-page">
      {/* Cabeçalho de navegação */}
      <header className="dashboard-header">
        <div className="dashboard-header-content">
          <h1>GovIntel AI — Busca Semântica</h1>
          <nav className="nav-links">
            <Link href="/dashboard" className="btn-link">
              ← Dashboard
            </Link>
          </nav>
        </div>
      </header>

      <main className="search-main">
        {/* Formulário de busca */}
        <section
          className="search-form-section"
          aria-labelledby="search-heading"
        >
          <h2 id="search-heading" className="sr-only">
            Busca semântica
          </h2>
          <form
            id="search-form"
            onSubmit={handleSubmit}
            className="search-form"
            noValidate
          >
            <div className="search-input-group">
              <label htmlFor="search-query" className="sr-only">
                Consulta
              </label>
              <input
                id="search-query"
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="O que você procura neste edital?"
                required
                className="search-input"
              />
              <button
                id="search-submit-btn"
                type="submit"
                className="btn-primary"
                disabled={state.phase === "loading" || !query.trim()}
              >
                {state.phase === "loading" ? "Buscando…" : "Buscar"}
              </button>
            </div>

            {/* Filtro por edital */}
            <div className="search-filter-row">
              <label htmlFor="search-tender-filter">Filtrar por edital:</label>
              <select
                id="search-tender-filter"
                value={selectedTenderId}
                onChange={(e) => setSelectedTenderId(e.target.value)}
                disabled={loadingTenders}
              >
                <option value="">Todos os editais</option>
                {tenders.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.title}
                  </option>
                ))}
              </select>
            </div>
          </form>
        </section>

        {/* Resultados */}
        <section className="search-results-section" aria-live="polite">
          {/* Estado: carregando */}
          {state.phase === "loading" && (
            <p id="search-loading" role="status" className="search-status">
              Buscando…
            </p>
          )}

          {/* Estado: erro */}
          {state.phase === "error" && (
            <div id="search-error" className="alert-error" role="alert">
              {state.error}
            </div>
          )}

          {/* Estado: vazio */}
          {state.phase === "done" && state.results.length === 0 && (
            <p id="search-empty" className="search-status search-empty">
              Nenhum resultado encontrado para &ldquo;{query}&rdquo;.
            </p>
          )}

          {/* Lista de resultados */}
          {state.phase === "done" && state.results.length > 0 && (
            <>
              <p className="search-summary">
                {state.totalItems} resultado(s) — página {state.currentPage} de{" "}
                {state.totalPages}
              </p>
              <ul
                id="search-results-list"
                className="search-results-list"
                aria-label="Resultados da busca"
              >
                {state.results.map((item) => (
                  <li key={item.chunkId} className="search-result-item">
                    <div className="search-result-header">
                      <span className="search-result-page">
                        Página {item.pageNumber}
                      </span>
                      <span
                        className="search-result-score"
                        aria-label={`Score de relevância: ${(item.score * 100).toFixed(0)}%`}
                      >
                        {(item.score * 100).toFixed(0)}% relevante
                      </span>
                    </div>
                    <p className="search-result-snippet">{item.snippet}</p>
                    <div className="search-result-actions">
                      <Link
                        href={`/chat?tenderId=${item.tenderId}`}
                        className="btn-link"
                      >
                        Chat sobre este edital
                      </Link>
                    </div>
                  </li>
                ))}
              </ul>

              {/* Paginação */}
              {state.totalPages > 1 && (
                <nav
                  className="pagination"
                  aria-label="Paginação dos resultados de busca"
                >
                  <button
                    id="search-prev-btn"
                    className="btn-secondary"
                    onClick={() =>
                      handlePageChange(Math.max(1, state.currentPage - 1))
                    }
                    disabled={state.currentPage === 1}
                  >
                    ← Anterior
                  </button>
                  <span>
                    Página {state.currentPage} de {state.totalPages}
                  </span>
                  <button
                    id="search-next-btn"
                    className="btn-secondary"
                    onClick={() =>
                      handlePageChange(
                        Math.min(state.totalPages, state.currentPage + 1),
                      )
                    }
                    disabled={state.currentPage === state.totalPages}
                  >
                    Próxima →
                  </button>
                </nav>
              )}
            </>
          )}
        </section>
      </main>
    </div>
  );
}
