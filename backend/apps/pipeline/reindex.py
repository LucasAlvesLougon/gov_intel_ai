"""Reindexação de embeddings com staging e promoção atômica do corpus selecionado."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from django.db import transaction

from apps.intelligence.cache import increment_company_data_revision
from apps.intelligence.embeddings import get_embedding_metadata
from apps.pipeline.chunker import create_chunks_from_pages
from apps.pipeline.models import DocumentChunk
from apps.pipeline.pdf_extractor import extract_pdf_pages
from apps.tenders.models import Tender
from apps.tenders.storage import get_storage_adapter


class ReindexError(RuntimeError):
    """Falha segura que impede a promoção parcial de uma reindexação."""


@dataclass(frozen=True)
class StagedTender:
    tender_id: str
    previous_generation: int
    target_generation: int
    previous_chunk_count: int
    staged_chunk_count: int


def _metadata_filters(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "embedding_provider": metadata["provider"],
        "embedding_model_name": metadata["model_name"],
        "embedding_model_version": metadata["model_version"],
        "embedding_dimensions": metadata["dimensions"],
        "normalization": metadata["normalization"],
        "preprocessing_fingerprint": metadata["preprocessing_fingerprint"],
    }


def _cleanup_staged(staged: Iterable[StagedTender]) -> None:
    for item in staged:
        DocumentChunk.objects.filter(
            tender_id=item.tender_id,
            generation=item.target_generation,
            staged=True,
        ).delete()


def _invalidate_company_cache(company_ids: set[str]) -> None:
    """Não transforme falha de cache pós-commit em falso rollback do banco."""
    for company_id in company_ids:
        try:
            increment_company_data_revision(company_id)
        except Exception:
            # A identidade do embedding também está na chave do cache; uma
            # falha transitória do Redis não pode reportar uma promoção já
            # confirmada como se ela tivesse sido revertida.
            continue


def _stage_tender(
    tender: Tender,
    adapter: Any,
    metadata: dict[str, Any],
) -> StagedTender:
    """Extrai e grava uma edição como staged sem alterar a geração corrente."""
    previous_generation = tender.pipeline_generation
    target_generation = previous_generation + 1
    previous_chunk_count = DocumentChunk.objects.filter(
        tender=tender, is_current=True
    ).count()

    # Sobras de uma execução interrompida são sempre descartáveis: nunca são
    # current e pertencem exatamente à geração que será reconstituída.
    DocumentChunk.objects.filter(
        tender=tender, generation=target_generation, staged=True
    ).delete()

    storage = get_storage_adapter()
    pages = extract_pdf_pages(storage.read_bytes(tender.storage_key))
    chunk_payloads = create_chunks_from_pages(pages)
    if not chunk_payloads:
        raise ReindexError(f"Nenhum chunk foi extraído para o edital {tender.id}.")

    embeddings = adapter.embed_documents_batch(
        [(tender.title, chunk.text) for chunk in chunk_payloads]
    )
    if len(embeddings) != len(chunk_payloads):
        raise ReindexError("O provider retornou quantidade de embeddings inconsistente.")

    chunks_to_create = [
        DocumentChunk(
            company=tender.company,
            tender=tender,
            generation=target_generation,
            chunk_index=chunk.chunk_index,
            page_number=chunk.page_number,
            start_char_offset=chunk.start_char_offset,
            end_char_offset=chunk.end_char_offset,
            text=chunk.text,
            text_hash=chunk.text_hash,
            embedding=embeddings[index],
            **_metadata_filters(metadata),
            is_current=False,
            staged=True,
        )
        for index, chunk in enumerate(chunk_payloads)
    ]
    DocumentChunk.objects.bulk_create(chunks_to_create)
    return StagedTender(
        tender_id=str(tender.id),
        previous_generation=previous_generation,
        target_generation=target_generation,
        previous_chunk_count=previous_chunk_count,
        staged_chunk_count=len(chunks_to_create),
    )


def stage_tender(
    tender: Tender,
    adapter: Any,
    metadata: dict[str, Any],
) -> StagedTender:
    """Garante que uma falha durante o edital não deixe staging órfão."""
    try:
        return _stage_tender(tender, adapter, metadata)
    except Exception:
        DocumentChunk.objects.filter(
            tender=tender,
            generation=tender.pipeline_generation + 1,
            staged=True,
        ).delete()
        raise


def promote_staged(
    staged: list[StagedTender],
    metadata: dict[str, Any],
) -> None:
    """Promove todos os editais staged juntos ou não promove nenhum."""
    if not staged:
        return

    tender_ids = [item.tender_id for item in staged]
    staged_by_id = {item.tender_id: item for item in staged}
    companies: set[str] = set()

    with transaction.atomic():
        locked_tenders = list(
            Tender.objects.select_for_update()
            .select_related("company")
            .filter(id__in=tender_ids)
            .order_by("id")
        )
        if len(locked_tenders) != len(staged):
            raise ReindexError("O conjunto de editais mudou durante a reindexação.")

        for tender in locked_tenders:
            item = staged_by_id[str(tender.id)]
            if tender.pipeline_generation != item.previous_generation:
                raise ReindexError(
                    f"O edital {tender.id} mudou de geração durante a reindexação."
                )
            staged_qs = DocumentChunk.objects.filter(
                tender=tender,
                generation=item.target_generation,
                staged=True,
                is_current=False,
                **_metadata_filters(metadata),
            )
            if staged_qs.count() != item.staged_chunk_count:
                raise ReindexError(
                    f"Chunks staged inconsistentes para o edital {tender.id}."
                )

        for tender in locked_tenders:
            item = staged_by_id[str(tender.id)]
            DocumentChunk.objects.filter(tender=tender, is_current=True).update(
                is_current=False
            )
            DocumentChunk.objects.filter(
                tender=tender,
                generation=item.target_generation,
                staged=True,
            ).update(is_current=True, staged=False)
            tender.status = "PROCESSED"
            tender.progress = 100
            tender.processed_chunks = item.staged_chunk_count
            tender.pipeline_generation = item.target_generation
            tender.error_code = None
            tender.error_message = None
            tender.processing_lease_until = None
            tender.save(
                update_fields=[
                    "status",
                    "progress",
                    "processed_chunks",
                    "pipeline_generation",
                    "error_code",
                    "error_message",
                    "processing_lease_until",
                    "updated_at",
                ]
            )
            companies.add(str(tender.company_id))

    _invalidate_company_cache(companies)


def reindex_tenders(tenders: list[Tender], adapter: Any) -> list[StagedTender]:
    """Executa staging completo e promoção all-or-nothing dos editais."""
    metadata = get_embedding_metadata(adapter)
    staged: list[StagedTender] = []
    try:
        for tender in tenders:
            staged.append(stage_tender(tender, adapter, metadata))
        promote_staged(staged, metadata)
        return staged
    except Exception:
        _cleanup_staged(staged)
        raise


def rollback_tender(tender: Tender, generation: int) -> int:
    """Reativa uma geração anterior preservada após uma promoção."""
    companies: set[str] = set()
    with transaction.atomic():
        locked = Tender.objects.select_for_update().get(id=tender.id)
        if generation >= locked.pipeline_generation:
            raise ReindexError("A geração de rollback deve ser anterior à atual.")
        target = DocumentChunk.objects.filter(
            tender=locked,
            generation=generation,
            staged=False,
            embedding__isnull=False,
        )
        chunk_count = target.count()
        if chunk_count == 0:
            raise ReindexError("A geração de rollback não possui chunks válidos.")
        DocumentChunk.objects.filter(tender=locked, is_current=True).update(
            is_current=False
        )
        target.update(is_current=True)
        locked.pipeline_generation = generation
        locked.processed_chunks = chunk_count
        locked.status = "PROCESSED"
        locked.progress = 100
        locked.error_code = None
        locked.error_message = None
        locked.save(
            update_fields=[
                "pipeline_generation",
                "processed_chunks",
                "status",
                "progress",
                "error_code",
                "error_message",
                "updated_at",
            ]
        )
        companies.add(str(locked.company_id))

    _invalidate_company_cache(companies)
    return chunk_count
