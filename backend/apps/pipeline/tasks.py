import uuid
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.intelligence.cache import increment_company_data_revision
from apps.intelligence.embeddings import get_embedding_adapter, get_embedding_metadata
from apps.pipeline.chunker import create_chunks_from_pages
from apps.pipeline.exceptions import safe_pipeline_storage_message
from apps.pipeline.models import DocumentChunk
from apps.pipeline.pdf_extractor import extract_pdf_pages
from apps.tenders.models import Tender
from apps.tenders.storage import get_storage_adapter


@shared_task(name="pipeline.process_tender.v1", bind=True, max_retries=3)
def process_tender_v1(self, tender_id: str, job_id: str):
    """
    Processa um edital de forma assíncrona.
    - Idempotência por job_id
    - Extração por página com pypdf
    - Chunking com offsets exatos
    - Staged generation swap atômico
    - Safe error handling e atualização de status
    """
    # 1. Obter tender e derivar tenant a partir do banco
    tender = Tender.objects.filter(id=tender_id).select_related("company").first()
    if not tender:
        return {"status": "ERROR", "reason": "TENDER_NOT_FOUND"}

    job_uuid = uuid.UUID(str(job_id))

    # 2. Idempotência por job_id
    if tender.status == "PROCESSED" and tender.processing_job_id == job_uuid:
        return {"status": "PROCESSED", "tender_id": str(tender.id)}

    # 3. Determinar target generation
    if tender.status == "PROCESSED":
        target_generation = tender.pipeline_generation + 1
    else:
        target_generation = tender.pipeline_generation

    # 4. Iniciar processamento com lease
    with transaction.atomic():
        t = Tender.objects.select_for_update().get(id=tender.id)
        t.status = "PROCESSING"
        t.processing_job_id = job_uuid
        t.processing_lease_until = timezone.now() + timedelta(minutes=5)
        t.progress = 10
        t.error_code = None
        t.error_message = None
        t.save()

    try:
        # 5. Ler arquivo do storage privado
        storage = get_storage_adapter()
        file_bytes = storage.read_bytes(tender.storage_key)

        # 6. Extrair páginas
        pages = extract_pdf_pages(file_bytes)

        # Atualizar progresso
        Tender.objects.filter(id=tender.id).update(progress=40)

        # 7. Criar chunks
        chunk_payloads = create_chunks_from_pages(pages)

        # Atualizar progresso
        Tender.objects.filter(id=tender.id).update(progress=60)

        # 8. Gerar embeddings e persistir chunks como STAGED
        DocumentChunk.objects.filter(
            tender=tender, generation=target_generation, staged=True
        ).delete()

        adapter = get_embedding_adapter()
        embedding_metadata = get_embedding_metadata(adapter)
        doc_inputs = [(tender.title, chunk.text) for chunk in chunk_payloads]
        embeddings = adapter.embed_documents_batch(doc_inputs)

        # Atualizar progresso
        Tender.objects.filter(id=tender.id).update(progress=80)

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
                embedding=embeddings[idx],
                embedding_provider=embedding_metadata["provider"],
                embedding_model_name=embedding_metadata["model_name"],
                embedding_model_version=embedding_metadata["model_version"],
                embedding_dimensions=embedding_metadata["dimensions"],
                normalization=embedding_metadata["normalization"],
                preprocessing_fingerprint=embedding_metadata["preprocessing_fingerprint"],
                is_current=False,
                staged=True,
            )
            for idx, chunk in enumerate(chunk_payloads)
        ]
        DocumentChunk.objects.bulk_create(chunks_to_create)

        # 9. Atomic swap da geração staged para current
        with transaction.atomic():
            locked_tender = Tender.objects.select_for_update().get(id=tender.id)
            # Compare-and-set: verificar se a task é a detentora do job_id atual
            if locked_tender.processing_job_id != job_uuid:
                DocumentChunk.objects.filter(
                    tender=tender, generation=target_generation, staged=True
                ).delete()
                return {"status": "ABORTED", "reason": "STALE_JOB"}

            # Desativa geração anterior
            DocumentChunk.objects.filter(tender=locked_tender, is_current=True).update(
                is_current=False
            )
            # Ativa geração staged atual
            DocumentChunk.objects.filter(
                tender=locked_tender, generation=target_generation, staged=True
            ).update(is_current=True, staged=False)

            locked_tender.status = "PROCESSED"
            locked_tender.progress = 100
            locked_tender.processed_chunks = len(chunks_to_create)
            locked_tender.pipeline_generation = target_generation
            locked_tender.error_code = None
            locked_tender.error_message = None
            locked_tender.processing_lease_until = None
            locked_tender.save()

            # Invalidação de cache de busca para o tenant do edital
            increment_company_data_revision(tender.company_id)

        return {
            "status": "PROCESSED",
            "tender_id": str(tender.id),
            "chunks": len(chunks_to_create),
        }

    except Exception as exc:
        # 10. Falha: descarta staged chunks e transiciona para FAILED
        DocumentChunk.objects.filter(
            tender=tender, generation=target_generation, staged=True
        ).delete()

        error_code = getattr(exc, "code", "PROCESSING_FAILED")
        if error_code not in {
            "PDF_INVALID",
            "PDF_ENCRYPTED",
            "NO_TEXT_EXTRACTED",
            "PAGE_LIMIT_EXCEEDED",
            "CHAR_LIMIT_EXCEEDED",
        }:
            error_code = "PROCESSING_FAILED"
        error_message = safe_pipeline_storage_message(error_code)

        Tender.objects.filter(id=tender.id).update(
            status="FAILED",
            error_code=error_code,
            error_message=error_message,
            processing_lease_until=None,
        )
        return {
            "status": "FAILED",
            "error_code": error_code,
            "error_message": error_message,
        }
