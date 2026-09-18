import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.models import Company, User
from apps.pipeline.models import DocumentChunk, OutboxMessage
from apps.pipeline.outbox import process_outbox_batch, reconcile_stale_processing_tenders
from apps.pipeline.tasks import process_tender_v1
from apps.tenders.models import Tender
from apps.tenders.storage import get_storage_adapter
from tests.fixtures.pdf_helpers import create_minimal_text_pdf

pytestmark = pytest.mark.django_db


@pytest.fixture
def test_company():
    return Company.objects.create(name="Pipeline Test Corp")


@pytest.fixture
def test_user(test_company):
    return User.objects.create_user(
        email="pipeline@test.com",
        password="Password123!",
        company=test_company,
    )


def test_process_tender_success_creates_chunks_and_updates_status(test_company):
    # Setup PDF
    pdf_bytes = create_minimal_text_pdf(
        ["Edital 01/2026 - Concorrencia Publica", "Especificacoes tecnicas do objeto"]
    )
    tender_id = uuid.uuid4()
    job_id = uuid.uuid4()

    adapter = get_storage_adapter()
    storage_key = adapter.save(test_company.id, tender_id, pdf_bytes)

    tender = Tender.objects.create(
        id=tender_id,
        company=test_company,
        title="Edital Pipeline 01",
        status="PENDING",
        storage_key=storage_key,
        original_filename="edital01.pdf",
        file_size=len(pdf_bytes),
    )

    # Executa a task diretamente
    res = process_tender_v1(str(tender_id), str(job_id))
    assert res["status"] == "PROCESSED"

    tender.refresh_from_db()
    assert tender.status == "PROCESSED"
    assert tender.progress == 100
    assert tender.processed_chunks == 2
    assert tender.error_code is None
    assert tender.error_message is None

    chunks = DocumentChunk.objects.filter(tender=tender)
    assert chunks.count() == 2
    assert all(c.is_current is True for c in chunks)
    assert all(c.staged is False for c in chunks)
    assert all(c.embedding is not None for c in chunks)
    assert all(len(c.embedding) == 768 for c in chunks)
    assert all(c.embedding_provider == "mock" for c in chunks)

    chunk_1 = chunks.filter(page_number=1).first()
    assert chunk_1 is not None
    assert "Concorrencia Publica" in chunk_1.text
    assert chunk_1.start_char_offset == 0
    assert chunk_1.end_char_offset == len(chunk_1.text)


def test_process_tender_provider_failure_does_not_mark_processed(test_company):
    from unittest.mock import patch

    pdf_bytes = create_minimal_text_pdf(["Edital para testar falha de embedding."])
    tender_id = uuid.uuid4()
    job_id = uuid.uuid4()

    adapter = get_storage_adapter()
    storage_key = adapter.save(test_company.id, tender_id, pdf_bytes)

    tender = Tender.objects.create(
        id=tender_id,
        company=test_company,
        title="Edital Falha Provider",
        status="PENDING",
        storage_key=storage_key,
        original_filename="falha_provider.pdf",
        file_size=len(pdf_bytes),
    )

    with patch("apps.pipeline.tasks.get_embedding_adapter") as mock_get_adapter:
        mock_adapter = mock_get_adapter.return_value
        mock_adapter.embed_documents_batch.side_effect = RuntimeError("Gemini API rate limit")

        res = process_tender_v1(str(tender_id), str(job_id))
        assert res["status"] == "FAILED"

    tender.refresh_from_db()
    assert tender.status == "FAILED"
    assert tender.status != "PROCESSED"
    # Chunks da tentativa staged foram descartados
    assert DocumentChunk.objects.filter(tender=tender).count() == 0


def test_process_tender_idempotent_redelivery_does_not_duplicate_chunks(test_company):
    pdf_bytes = create_minimal_text_pdf(["Pagina unica com conteudo do edital."])
    tender_id = uuid.uuid4()
    job_id = uuid.uuid4()

    adapter = get_storage_adapter()
    storage_key = adapter.save(test_company.id, tender_id, pdf_bytes)

    tender = Tender.objects.create(
        id=tender_id,
        company=test_company,
        title="Edital Idempotente",
        status="PENDING",
        storage_key=storage_key,
        original_filename="edital_idem.pdf",
        file_size=len(pdf_bytes),
    )

    # Primeira execução
    process_tender_v1(str(tender_id), str(job_id))
    assert DocumentChunk.objects.filter(tender=tender).count() == 1

    # Redelivery com mesmo jobId
    process_tender_v1(str(tender_id), str(job_id))
    assert DocumentChunk.objects.filter(tender=tender).count() == 1


def test_process_tender_corrupted_pdf_transitions_to_failed(test_company):
    corrupted_bytes = b"%PDF-1.4\nCorrupted content not a valid PDF"
    tender_id = uuid.uuid4()
    job_id = uuid.uuid4()

    adapter = get_storage_adapter()
    storage_key = adapter.save(test_company.id, tender_id, corrupted_bytes)

    tender = Tender.objects.create(
        id=tender_id,
        company=test_company,
        title="Edital Corrompido",
        status="PENDING",
        storage_key=storage_key,
        original_filename="corrompido.pdf",
        file_size=len(corrupted_bytes),
    )

    process_tender_v1(str(tender_id), str(job_id))

    tender.refresh_from_db()
    assert tender.status == "FAILED"
    assert tender.error_code == "PDF_INVALID"
    assert "Falha" in tender.error_message
    assert DocumentChunk.objects.filter(tender=tender).count() == 0


def test_staged_swap_preserves_previous_generation_on_failure(test_company):
    # Simula geração 1 já processada e corrente
    tender = Tender.objects.create(
        company=test_company,
        title="Edital Geracoes",
        status="PROCESSED",
        pipeline_generation=1,
    )
    old_chunk = DocumentChunk.objects.create(
        company=test_company,
        tender=tender,
        generation=1,
        chunk_index=0,
        page_number=1,
        start_char_offset=0,
        end_char_offset=20,
        text="Conteudo geracao 1",
        text_hash="hash1",
        is_current=True,
        staged=False,
    )

    # Nova tentativa de processamento com PDF corrompido
    corrupted_bytes = b"%PDF-1.4\nInvalido"
    adapter = get_storage_adapter()
    storage_key = adapter.save(test_company.id, tender.id, corrupted_bytes)
    tender.storage_key = storage_key
    tender.save()

    process_tender_v1(str(tender.id), str(uuid.uuid4()))

    # A geração antiga permanece intacta como is_current=True
    old_chunk.refresh_from_db()
    assert old_chunk.is_current is True
    assert DocumentChunk.objects.filter(tender=tender, generation=2).count() == 0


def test_corpus_reindex_promotes_all_tenders_atomically(test_company):
    from apps.intelligence.embeddings import get_embedding_adapter
    from apps.pipeline.reindex import reindex_tenders, rollback_tender

    pdf_bytes = create_minimal_text_pdf(["Conteudo estável para reindexação."])
    tenders = []
    storage = get_storage_adapter()
    for index in range(2):
        tender_id = uuid.uuid4()
        storage_key = storage.save(test_company.id, tender_id, pdf_bytes)
        tender = Tender.objects.create(
            id=tender_id,
            company=test_company,
            title=f"Edital Reindex {index}",
            status="PENDING",
            storage_key=storage_key,
            original_filename=f"reindex-{index}.pdf",
            file_size=len(pdf_bytes),
        )
        process_tender_v1(str(tender.id), str(uuid.uuid4()))
        tenders.append(Tender.objects.get(id=tender.id))

    staged = reindex_tenders(tenders, get_embedding_adapter())

    assert len(staged) == 2
    for tender in Tender.objects.filter(id__in=[item.id for item in tenders]):
        tender.refresh_from_db()
        assert tender.pipeline_generation == 2
        assert DocumentChunk.objects.filter(
            tender=tender, generation=1, is_current=True
        ).count() == 0
        assert DocumentChunk.objects.filter(
            tender=tender, generation=2, is_current=True, staged=False
        ).count() == 1

    rollback_tender(Tender.objects.get(id=tenders[0].id), 1)
    rolled_back = Tender.objects.get(id=tenders[0].id)
    assert rolled_back.pipeline_generation == 1
    assert DocumentChunk.objects.filter(
        tender=rolled_back, generation=1, is_current=True
    ).count() == 1


def test_corpus_reindex_failure_preserves_every_current_generation(test_company):
    from unittest.mock import patch

    from apps.intelligence.embeddings import get_embedding_adapter
    from apps.pipeline.reindex import reindex_tenders

    pdf_bytes = create_minimal_text_pdf(["Conteudo antigo que deve permanecer."])
    tenders = []
    storage = get_storage_adapter()
    for index in range(2):
        tender_id = uuid.uuid4()
        storage_key = storage.save(test_company.id, tender_id, pdf_bytes)
        tender = Tender.objects.create(
            id=tender_id,
            company=test_company,
            title=f"Edital Rollback {index}",
            status="PENDING",
            storage_key=storage_key,
            original_filename=f"rollback-{index}.pdf",
            file_size=len(pdf_bytes),
        )
        process_tender_v1(str(tender.id), str(uuid.uuid4()))
        tenders.append(Tender.objects.get(id=tender.id))

    with patch(
        "apps.pipeline.reindex.stage_tender",
        side_effect=RuntimeError("falha controlada"),
    ):
        with pytest.raises(RuntimeError, match="falha controlada"):
            reindex_tenders(tenders, get_embedding_adapter())

    for tender in Tender.objects.filter(id__in=[item.id for item in tenders]):
        tender.refresh_from_db()
        assert tender.pipeline_generation == 1
        assert DocumentChunk.objects.filter(
            tender=tender, generation=1, is_current=True
        ).count() == 1
        assert DocumentChunk.objects.filter(
            tender=tender, generation=2
        ).count() == 0


def test_outbox_transactional_creation_on_upload(client, test_user):
    from apps.core.jwt_utils import get_tokens_for_user

    tokens = get_tokens_for_user(test_user)
    access_token = tokens["access"]

    from django.core.files.uploadedfile import SimpleUploadedFile

    pdf_bytes = create_minimal_text_pdf(["Edital via Upload API"])
    uploaded = SimpleUploadedFile("upload.pdf", pdf_bytes, content_type="application/pdf")

    res = client.post(
        "/api/tenders/",
        {"file": uploaded, "title": "Edital Upload Outbox"},
        format="multipart",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
    )
    assert res.status_code == 202
    tender_id = res.json()["id"]

    # Mensagem de outbox foi criada na mesma transação
    msg = OutboxMessage.objects.filter(payload__tenderId=tender_id).first()
    assert msg is not None
    assert msg.status in ["PENDING", "SENT"]
    assert msg.topic == "pipeline.process_tender.v1"


def test_outbox_relay_processes_pending_message(test_company):
    tender = Tender.objects.create(
        company=test_company,
        title="Edital Relay",
        status="PENDING",
    )
    msg = OutboxMessage.objects.create(
        topic="pipeline.process_tender.v1",
        routing_key="pipeline",
        payload={"tenderId": str(tender.id), "jobId": str(uuid.uuid4())},
        status="PENDING",
    )

    # Processa lote do outbox
    processed_count = process_outbox_batch()
    assert processed_count >= 1

    msg.refresh_from_db()
    assert msg.status == "SENT"


def test_reconciler_recovers_stale_processing_tender(test_company):
    tender = Tender.objects.create(
        company=test_company,
        title="Edital Preso",
        status="PROCESSING",
        processing_lease_until=timezone.now() - timedelta(minutes=10),
    )

    recovered = reconcile_stale_processing_tenders()
    assert recovered >= 1

    tender.refresh_from_db()
    assert tender.status == "FAILED"
    assert tender.error_code == "PROCESSING_TIMEOUT"
