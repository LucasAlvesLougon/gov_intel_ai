import re
import unicodedata
import uuid
from typing import Any

from django.db import connection
from django.db.models import Q, QuerySet
from pgvector.django import CosineDistance

from apps.core.models import Company
from apps.intelligence.embeddings import get_embedding_adapter, get_embedding_metadata
from apps.pipeline.models import DocumentChunk

_STOP_WORDS = frozenset(
    (
        "a ao aos as com da das de do dos e em entre essa esse este esta eu foi há na "
        "não nas no nos o os para por qual quais que se sem ser sobre sua suas um uma "
        "uns umas como deverá deve será são este edital"
    ).split()
)


def _fold_text(value: str) -> str:
    """Normaliza acentos e caixa para comparação lexical estável em português."""
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _tokenize(value: str) -> set[str]:
    folded = _fold_text(value)
    return {
        token
        for token in re.findall(r"[^\W_]+", folded, flags=re.UNICODE)
        if len(token) > 2 and token not in _STOP_WORDS
    }


def _raw_search_terms(value: str) -> list[str]:
    """Retorna termos preservando acentos para o filtro SQL e o snippet."""
    terms: list[str] = []
    for token in re.findall(r"[^\W_]+", value, flags=re.UNICODE):
        if len(_fold_text(token)) > 2 and _fold_text(token) not in _STOP_WORDS:
            terms.append(token)
    return terms


def _lexical_score(query_text: str, chunk_text: str) -> float:
    query_tokens = _tokenize(query_text)
    if not query_tokens:
        return 0.0
    chunk_tokens = _tokenize(chunk_text)
    overlap = query_tokens.intersection(chunk_tokens)
    if not overlap:
        return 0.0
    coverage = len(overlap) / len(query_tokens)
    phrase_match = _fold_text(query_text).strip().rstrip("?!.") in _fold_text(chunk_text)
    return min(1.0, coverage * 0.85 + (0.15 if phrase_match else 0.0))


def _make_snippet(text: str, query_text: str | None, max_chars: int = 200) -> str:
    if len(text) <= max_chars or not query_text:
        return text[:max_chars]

    matches = [
        re.search(re.escape(term), text, flags=re.IGNORECASE)
        for term in _raw_search_terms(query_text)
    ]
    match = next((candidate for candidate in matches if candidate), None)
    if match is None:
        return text[:max_chars]

    start = max(0, match.start() - 80)
    end = min(len(text), start + max_chars)
    if end - start < max_chars:
        start = max(0, end - max_chars)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = f"…{snippet}"
    if end < len(text):
        snippet = f"{snippet}…"
    return snippet


class VectorSearchRepository:
    """
    Repositório de busca semântica com pgvector e distância cosseno.
    - Filtro obrigatório por empresa (multi-tenant estrito).
    - Somente chunks com is_current=True e embedding preenchido participam da busca.
    - Geração STAGED ou chunks inativos são completamente ignorados.
    - Suporte a filtro opcional por edital (tender_id).
    - Overfetch iterativo e fallback exato para cobrir tenants pequenos/enviesados.
    - Reranking lexical híbrido quando a consulta textual está disponível (inclui o mock local).
    - Resultados incluem score, página, offsets, texto e snippet.
    """

    def search(
        self,
        company: Company,
        query_vector: list[float],
        tender_id: uuid.UUID | str | None = None,
        top_k: int = 8,
        page: int = 1,
        page_size: int = 20,
        query_text: str | None = None,
    ) -> list[dict[str, Any]]:
        if not company or not query_vector:
            return []

        top_k = max(1, min(top_k, 50))

        embedding_metadata = get_embedding_metadata(get_embedding_adapter())
        base_qs: QuerySet[DocumentChunk] = DocumentChunk.objects.filter(
            company=company,
            is_current=True,
            embedding__isnull=False,
            embedding_provider=embedding_metadata["provider"],
            embedding_model_name=embedding_metadata["model_name"],
            embedding_model_version=embedding_metadata["model_version"],
            embedding_dimensions=embedding_metadata["dimensions"],
            normalization=embedding_metadata["normalization"],
            preprocessing_fingerprint=embedding_metadata["preprocessing_fingerprint"],
        )

        if tender_id:
            base_qs = base_qs.filter(tender_id=tender_id)

        available_count = base_qs.count()
        if available_count == 0:
            return []

        target_count = min(top_k, available_count)
        overfetch_limit = min(max(top_k * 2, top_k), available_count)

        # Ordenar por distância cosseno
        qs = base_qs.annotate(
            distance=CosineDistance("embedding", query_vector)
        ).order_by("distance")

        # Providers mockados não têm semântica: seus vetores são apenas
        # determinísticos. Quando há uma consulta textual, amplia-se o conjunto
        # de candidatos e usa-se sobreposição lexical como reranking híbrido.
        candidate_limit = overfetch_limit
        if query_text:
            candidate_limit = min(max(overfetch_limit, top_k * 10, 100), available_count)
        chunks = list(qs[:candidate_limit])

        if query_text and available_count > candidate_limit:
            lexical_filter = Q()
            for term in _raw_search_terms(query_text):
                lexical_filter |= Q(text__icontains=term)
            if lexical_filter:
                lexical_chunks = list(qs.filter(lexical_filter)[:candidate_limit])
                seen_ids = {chunk.id for chunk in chunks}
                chunks.extend(chunk for chunk in lexical_chunks if chunk.id not in seen_ids)

        # Se overfetch no HNSW retornar menos que o esperado, executa fallback exato
        if len(chunks) < target_count:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL enable_indexscan = off")
                cursor.execute("SET LOCAL enable_bitmapscan = off")
                chunks = list(qs[:top_k])

        ranked_chunks: list[tuple[float, float, DocumentChunk]] = []
        for chunk in chunks:
            raw_dist = float(chunk.distance) if hasattr(chunk, "distance") else 0.0
            vector_similarity = max(0.0, 1.0 - raw_dist)
            lexical_similarity = (
                _lexical_score(query_text, chunk.text) if query_text else 0.0
            )
            similarity = max(vector_similarity, lexical_similarity)
            ranked_chunks.append((similarity, vector_similarity, chunk))

        if query_text:
            ranked_chunks.sort(key=lambda item: (-item[0], -item[1], item[2].chunk_index))
        else:
            ranked_chunks.sort(key=lambda item: (-item[0], item[2].chunk_index))

        results = []
        for similarity, _vector_similarity, chunk in ranked_chunks[:top_k]:
            snippet = _make_snippet(chunk.text, query_text)
            results.append(
                {
                    "chunkId": str(chunk.id),
                    "companyId": str(chunk.company_id),
                    "tenderId": str(chunk.tender_id),
                    "pageNumber": chunk.page_number,
                    "startCharOffset": chunk.start_char_offset,
                    "endCharOffset": chunk.end_char_offset,
                    "text": chunk.text,
                    "snippet": snippet,
                    "score": round(similarity, 4),
                }
            )

        return results
