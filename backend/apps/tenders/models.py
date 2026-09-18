import uuid

from django.db import models

from apps.core.models import Company


class Tender(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("PROCESSING", "Processing"),
        ("PROCESSED", "Processed"),
        ("FAILED", "Failed"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="tenders",
        null=False,
        blank=False,
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="PENDING")
    original_filename = models.CharField(max_length=255)
    storage_key = models.CharField(max_length=512, blank=True, default="")
    file_size = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, default="")
    pipeline_generation = models.PositiveIntegerField(default=1)
    progress = models.PositiveIntegerField(default=0)
    processed_chunks = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=64, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    processing_job_id = models.UUIDField(null=True, blank=True)
    processing_lease_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenders_tender"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["PENDING", "PROCESSING", "PROCESSED", "FAILED"]),
                name="valid_tender_status",
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.status})"


class IdempotencyKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="idempotency_keys",
    )
    user = models.ForeignKey(
        "core.User",
        on_delete=models.CASCADE,
        related_name="idempotency_keys",
    )
    endpoint = models.CharField(max_length=255)
    key = models.CharField(max_length=255)
    request_hash = models.CharField(max_length=64)
    tender = models.ForeignKey(
        Tender,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="idempotency_records",
    )
    status_code = models.PositiveIntegerField(default=202)
    response_data = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenders_idempotency_key"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "user", "endpoint", "key"],
                name="unique_idempotency_key_per_tenant_user_endpoint",
            ),
        ]

    def __str__(self):
        return f"{self.endpoint}:{self.key} ({self.company_id})"
