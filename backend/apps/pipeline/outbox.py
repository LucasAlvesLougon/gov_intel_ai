import uuid
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.pipeline.exceptions import safe_pipeline_error_message
from apps.pipeline.models import OutboxMessage
from apps.pipeline.tasks import process_tender_v1
from apps.tenders.models import Tender


def schedule_tender_processing(tender: Tender, job_id: uuid.UUID | None = None) -> OutboxMessage:
    """Cria atomicamente um registro de outbox para agendar o processamento assíncrono do edital."""
    if job_id is None:
        job_id = uuid.uuid4()

    return OutboxMessage.objects.create(
        topic="pipeline.process_tender.v1",
        routing_key="pipeline",
        payload={
            "tenderId": str(tender.id),
            "jobId": str(job_id),
        },
        status="PENDING",
    )


def process_outbox_batch(batch_size: int = 50) -> int:
    """
    Processa um lote de mensagens do outbox com lease atômico e confirmação de publicação.
    Recupera rows com lease expirado e evita duplicate publishing concorrente.
    """
    now = timezone.now()
    processed_count = 0

    with transaction.atomic():
        pending_messages = list(
            OutboxMessage.objects.select_for_update(skip_locked=True)
            .filter(
                Q(status="PENDING")
                | Q(status="PROCESSING", lease_until__lt=now)
                | Q(status="FAILED", next_attempt_at__lte=now, attempts__lt=5)
            )
            .order_by("created_at")[:batch_size]
        )

        for msg in pending_messages:
            msg.status = "PROCESSING"
            msg.lease_until = now + timedelta(seconds=60)
            msg.attempts += 1
            msg.save()

    for msg in pending_messages:
        try:
            # Publica a task no Celery com routing para fila durável
            process_tender_v1.apply_async(
                kwargs={
                    "tender_id": msg.payload["tenderId"],
                    "job_id": msg.payload["jobId"],
                },
                queue="govintel.pipeline",
                routing_key="pipeline",
            )
            msg.status = "SENT"
            msg.lease_until = None
            msg.save(update_fields=["status", "lease_until", "updated_at"])
            processed_count += 1
        except Exception:
            msg.error_message = safe_pipeline_error_message("PROCESSING_FAILED")
            if msg.attempts >= msg.max_attempts:
                msg.status = "FAILED"
            else:
                msg.status = "PENDING"
                msg.next_attempt_at = timezone.now() + timedelta(seconds=2**msg.attempts)
            msg.lease_until = None
            msg.save(
                update_fields=[
                    "status",
                    "error_message",
                    "next_attempt_at",
                    "lease_until",
                    "updated_at",
                ]
            )

    return processed_count


def reconcile_stale_processing_tenders() -> int:
    """
    Varre e recupera editais que ficaram em PROCESSING com lease expirado.
    Finaliza com status FAILED e erro seguro PROCESSING_TIMEOUT.
    """
    now = timezone.now()
    stale_tenders = Tender.objects.filter(
        status="PROCESSING",
        processing_lease_until__lt=now,
    )
    count = stale_tenders.count()
    if count > 0:
        stale_tenders.update(
            status="FAILED",
            error_code="PROCESSING_TIMEOUT",
            error_message="O processamento do edital expirou e foi finalizado por timeout.",
            processing_lease_until=None,
        )
    return count
