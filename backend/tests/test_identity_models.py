import uuid

import pytest
from django.db import IntegrityError, transaction

from apps.core.models import Company, User

pytestmark = pytest.mark.django_db


def test_owner_has_uuid_tenant_and_hashed_password():
    company = Company.objects.create(name="Empresa de teste")
    user = User.objects.create_user(
        email=" OWNER@Example.com ",
        password="Test-only!742",
        company=company,
    )
    assert isinstance(user.pk, uuid.UUID)
    assert user.email == "owner@example.com"
    assert user.role == "OWNER"
    assert user.company_id == company.pk
    assert user.check_password("Test-only!742")
    assert user.password != "Test-only!742"


def test_email_is_case_insensitive_unique_in_database():
    company = Company.objects.create(name="Empresa A")
    User.objects.create_user(email="owner@example.com", password="Test-only!742", company=company)
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create(email="OWNER@example.com", company=company)


def test_database_rejects_user_without_company():
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create(email="owner@example.com")


def test_companies_with_same_name_receive_different_slugs():
    first = Company.objects.create(name="Alfa Saúde")
    second = Company.objects.create(name="Alfa Saúde")
    assert first.slug.startswith("alfa-saude-")
    assert first.slug != second.slug


def test_database_rejects_unapproved_role():
    company = Company.objects.create(name="Empresa")
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create(email="owner@example.com", company=company, role="ADMIN")
