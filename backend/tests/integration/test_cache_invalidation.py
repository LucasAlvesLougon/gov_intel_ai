import uuid
from unittest.mock import patch

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.core.jwt_utils import get_tokens_for_user
from apps.core.models import Company, User
from apps.intelligence.repository import VectorSearchRepository
from apps.pipeline.models import DocumentChunk
from apps.pipeline.tasks import process_tender_v1
from apps.tenders.models import Tender
from apps.tenders.storage import get_storage_adapter
from tests.fixtures.pdf_helpers import create_minimal_text_pdf

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def company_a():
    return Company.objects.create(name="Tenant Cache Inv A")


@pytest.fixture
def company_b():
    return Company.objects.create(name="Tenant Cache Inv B")


@pytest.fixture
def user_a(company_a):
    return User.objects.create_user(
        email="invalidation_a@test.com",
        password="Password123!",
        company=company_a,
    )


@pytest.fixture
def user_b(company_b):
    return User.objects.create_user(
        email="invalidation_b@test.com",
        password="Password123!",
        company=company_b,
    )


@pytest.fixture
def auth_client_a(user_a):
    client = APIClient()
    tokens = get_tokens_for_user(user_a)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


@pytest.fixture
def auth_client_b(user_b):
    client = APIClient()
    tokens = get_tokens_for_user(user_b)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


def make_embedding(seed_val: float = 0.5, dim: int = 768) -> list[float]:
    vec = [0.0] * dim
    vec[0] = seed_val
    vec[1] = 1.0 - seed_val
    return vec


def test_tender_completion_invalidates_tenant_cache(auth_client_a, company_a):
    # 1. Tenant A já tem um edital processado com chunks
    tender_1 = Tender.objects.create(
        company=company_a,
        title="Edital Inicial",
        status="PROCESSED",
    )
    DocumentChunk.objects.create(
        company=company_a,
        tender=tender_1,
        generation=1,
        chunk_index=0,
        page_number=1,
        start_char_offset=0,
        end_char_offset=30,
        text="Licitacao de notebooks",
        text_hash="hash_note",
        embedding=make_embedding(0.8),
        is_current=True,
        staged=False,
    )

    payload = {"query": "notebooks"}

    # 2. Primeira busca (populates cache)
    res1 = auth_client_a.post("/api/search/semantic/", payload, format="json")
    assert res1.status_code == 200
    assert len(res1.json()["data"]) == 1

    # Confirma que segunda busca é cache hit
    with patch("apps.intelligence.views.VectorSearchRepository.search") as mock_search:
        res_hit = auth_client_a.post("/api/search/semantic/", payload, format="json")
        assert res_hit.status_code == 200
        mock_search.assert_not_called()

    # 3. Novo edital é processado pelo worker
    pdf_bytes = create_minimal_text_pdf(["Licitacao adicional de notebooks para escolas"])
    tender_2_id = uuid.uuid4()
    job_id = uuid.uuid4()

    storage = get_storage_adapter()
    storage_key = storage.save(company_a.id, tender_2_id, pdf_bytes)

    Tender.objects.create(
        id=tender_2_id,
        company=company_a,
        title="Edital Notebooks 2",
        status="PENDING",
        storage_key=storage_key,
        original_filename="notebooks2.pdf",
        file_size=len(pdf_bytes),
    )

    process_res = process_tender_v1(str(tender_2_id), str(job_id))
    assert process_res["status"] == "PROCESSED"

    # 4. Nova busca do Tenant A deve ser Cache Miss (re-executa repositório e traz 2 resultados)
    with patch(
        "apps.intelligence.views.VectorSearchRepository.search",
        wraps=VectorSearchRepository().search,
    ) as mock_search:
        res_miss = auth_client_a.post("/api/search/semantic/", payload, format="json")
        assert res_miss.status_code == 200
        mock_search.assert_called_once()
        assert len(res_miss.json()["data"]) == 2


def test_invalidation_does_not_affect_other_tenant_cache(
    auth_client_a, auth_client_b, company_a, company_b
):
    # Tenant A edital
    tender_a = Tender.objects.create(company=company_a, title="Edital A", status="PROCESSED")
    DocumentChunk.objects.create(
        company=company_a,
        tender=tender_a,
        generation=1,
        chunk_index=0,
        page_number=1,
        start_char_offset=0,
        end_char_offset=20,
        text="Item A",
        text_hash="hash_a",
        embedding=make_embedding(0.9),
        is_current=True,
        staged=False,
    )

    # Tenant B edital
    tender_b = Tender.objects.create(company=company_b, title="Edital B", status="PROCESSED")
    DocumentChunk.objects.create(
        company=company_b,
        tender=tender_b,
        generation=1,
        chunk_index=0,
        page_number=1,
        start_char_offset=0,
        end_char_offset=20,
        text="Item B",
        text_hash="hash_b",
        embedding=make_embedding(0.9),
        is_current=True,
        staged=False,
    )

    payload = {"query": "Item"}

    # Ambos buscam e populam cache
    res_a1 = auth_client_a.post("/api/search/semantic/", payload, format="json")
    assert res_a1.status_code == 200
    res_b1 = auth_client_b.post("/api/search/semantic/", payload, format="json")
    assert res_b1.status_code == 200

    # Tenant A processa novo edital e tem seu cache invalidado
    pdf_bytes = create_minimal_text_pdf(["Item A novo"])
    tender_a2_id = uuid.uuid4()
    storage = get_storage_adapter()
    key = storage.save(company_a.id, tender_a2_id, pdf_bytes)
    Tender.objects.create(
        id=tender_a2_id,
        company=company_a,
        title="Edital A2",
        status="PENDING",
        storage_key=key,
        original_filename="a2.pdf",
        file_size=len(pdf_bytes),
    )
    process_tender_v1(str(tender_a2_id), str(uuid.uuid4()))

    # Tenant B busca novamente -> AINDA É CACHE HIT!
    with patch("apps.intelligence.views.VectorSearchRepository.search") as mock_search_b:
        res_b2 = auth_client_b.post("/api/search/semantic/", payload, format="json")
        assert res_b2.status_code == 200
        mock_search_b.assert_not_called()


def test_tender_deletion_invalidates_tenant_cache(auth_client_a, company_a):
    tender = Tender.objects.create(
        company=company_a, title="Edital Delete Cache", status="PROCESSED"
    )
    DocumentChunk.objects.create(
        company=company_a,
        tender=tender,
        generation=1,
        chunk_index=0,
        page_number=1,
        start_char_offset=0,
        end_char_offset=20,
        text="Item a deletar",
        text_hash="hash_del",
        embedding=make_embedding(0.9),
        is_current=True,
        staged=False,
    )

    # 1. Busca e popula cache
    res1 = auth_client_a.post("/api/search/semantic/", {"query": "deletar"}, format="json")
    assert res1.status_code == 200
    assert len(res1.json()["data"]) == 1

    # 2. Deleta o edital via API
    del_res = auth_client_a.delete(f"/api/tenders/{tender.id}/")
    assert del_res.status_code == 204

    # 3. Busca novamente -> Cache Miss e resultados vazios
    with patch(
        "apps.intelligence.views.VectorSearchRepository.search",
        wraps=VectorSearchRepository().search,
    ) as mock_search:
        res2 = auth_client_a.post("/api/search/semantic/", {"query": "deletar"}, format="json")
        assert res2.status_code == 200
        mock_search.assert_called_once()
        assert len(res2.json()["data"]) == 0

