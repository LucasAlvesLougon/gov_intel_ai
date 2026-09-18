import uuid

from django.db import models
from pgvector.django import HnswIndex, VectorField

from apps.core.models import Company
from apps.tenders.models import Tender


class OutboxMessage(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("PROCESSING", "Processing"),
        ("SENT", "Sent"),
        ("FAILED", "Failed"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    topic = models.CharField(max_length=255, default="pipeline.process_tender.v1")
    routing_key = models.CharField(max_length=255, default="pipeline")
    payload = models.JSONField()
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="PENDING")
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)
    lease_until = models.DateTimeField(null=True, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pipeline_outbox"
        ordering = ["created_at"]

    def __str__(self):
        return f"OutboxMessage({self.topic}, status={self.status})"


class DocumentChunk(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="document_chunks",
    )
    tender = models.ForeignKey(
        Tender,
        on_delete=models.CASCADE,
        related_name="document_chunks",
    )
    generation = models.PositiveIntegerField(default=1)
    chunk_index = models.PositiveIntegerField()
    page_number = models.PositiveIntegerField()
    start_char_offset = models.PositiveIntegerField()
    end_char_offset = models.PositiveIntegerField()
    text = models.TextField()
    text_hash = models.CharField(max_length=64)
    embedding = VectorField(dimensions=768, null=True, blank=True)
    # Provider is part of the vector-space identity. Legacy rows are migrated
    # away from the active index until they are reindexed explicitly.
    embedding_provider = models.CharField(max_length=32, default="mock")
    embedding_model_name = models.CharField(max_length=64, default="mock-embedding-v1")
    embedding_model_version = models.CharField(max_length=64, default="v1")
    embedding_dimensions = models.PositiveIntegerField(default=768)
    normalization = models.CharField(max_length=32, default="NFKC")
    preprocessing_fingerprint = models.CharField(
        max_length=64, default="v2-pdf-layout-ocr-sentence"
    )
    is_current = models.BooleanField(default=False)
    staged = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pipeline_document_chunk"
        ordering = ["generation", "chunk_index"]
        indexes = [
            models.Index(fields=["company", "is_current"], name="doc_chunk_comp_curr_idx"),
            HnswIndex(
                name="doc_chunk_embedding_hnsw_idx",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tender", "generation", "chunk_index"],
                name="unique_chunk_per_tender_generation_index",
            ),
        ]

    def __str__(self):
        return f"Chunk(tender={self.tender_id}, gen={self.generation}, idx={self.chunk_index})"
