import uuid

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import Company, User
from apps.tenders.models import Tender


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    tender = models.ForeignKey(
        Tender,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    title = models.CharField(max_length=255, default="Nova conversa")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "conversations_conversation"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["company", "user"], name="conv_company_user_idx"),
            models.Index(fields=["tender", "company"], name="conv_tender_company_idx"),
        ]

    def clean(self):
        super().clean()
        if self.tender_id and self.company_id:
            if self.tender.company_id != self.company_id:
                raise ValidationError("O edital deve pertencer à mesma empresa da conversa.")
            if self.tender.status != "PROCESSED":
                raise ValidationError(
                    "A conversa só pode ser criada para editais com status PROCESSED."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Conversation({self.id}, tender={self.tender_id}, user={self.user_id})"


class Message(models.Model):
    ROLE_CHOICES = (
        ("user", "User"),
        ("assistant", "Assistant"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    citations = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "conversations_message"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"], name="msg_conv_created_idx"),
        ]

    def __str__(self):
        return f"Message({self.id}, conv={self.conversation_id}, role={self.role})"
