import secrets
import uuid
from datetime import datetime

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils.text import slugify


class Company(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_company"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "company"
            while True:
                candidate = f"{base_slug}-{secrets.token_hex(4)}"
                if not Company.objects.filter(slug=candidate).exists():
                    self.slug = candidate
                    break
        super().save(*args, **kwargs)


class UserManager(BaseUserManager):
    def normalize_email(self, email):
        if not email:
            return ""
        return email.strip().lower()

    def create_user(self, email, password=None, company=None, **extra_fields):
        if not email:
            raise ValueError("O email é obrigatório.")
        normalized_email = self.normalize_email(email)
        extra_fields.setdefault("role", "OWNER")
        user = self.model(email=normalized_email, company=company, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "OWNER")
        return self.create_user(email, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ("OWNER", "Owner"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=255, unique=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="users",
        null=False,
        blank=False,
    )
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default="OWNER")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "core_user"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(Lower("email"), name="unique_case_insensitive_user_email"),
            models.CheckConstraint(
                condition=models.Q(role__in=["OWNER"]),
                name="valid_user_role",
            ),
        ]

    def __str__(self):
        return f"{self.email} ({self.role})"

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)


class RefreshTokenRecord(models.Model):
    """Estado server-side de cada refresh token para rotação e reuse detection."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="refresh_token_records",
    )
    family_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    jti = models.CharField(max_length=255, unique=True)
    replaced_by_jti = models.CharField(max_length=255, null=True, blank=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_refresh_token_record"
        indexes = [
            models.Index(
                fields=["family_id", "revoked_at"],
                name="refresh_family_revoked_idx",
            ),
        ]

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at <= now
