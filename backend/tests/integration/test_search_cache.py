from unittest.mock import patch

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.core.jwt_utils import get_tokens_for_user
from apps.core.models import Company, User
from apps.intelligence.cache import (
    generate_semantic_search_cache_key,
    increment_company_data_revision,
)
from apps.intelligence.repository import VectorSearchRepository
from apps.pipeline.models import DocumentChunk
from apps.tenders.models import Tender

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def company_a():
    return Company.objects.create(name="Empresa Cache Alpha")


@pytest.fixture
def company_b():
    return Company.objects.create(name="Empresa Cache Beta")


@pytest.fixture
def user_a(company_a):
    return User.objects.create_user(
        email="cache_alpha@test.com",
        password="Password123!",
        company=company_a,
    )


@pytest.fixture
def user_b(company_b):
    return User.objects.create_user(
        email="cache_beta@test.com",
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


def test_cache_key_structure_matches_contract(company_a):
    key = generate_semantic_search_cache_key(
        company_id=company_a.id,
        query="reforma escolar",
        tender_id=None,
        top_k=8,
        page=1,
        page_size=20,
    )
    parts = key.split(":")
    assert parts[0] == "govintel"
    assert parts[1] == "v1"
    assert parts[2] == "semantic"
    assert parts[3] == str(company_a.id)
    assert parts[4] == "company"  # scope
    assert parts[5].isdigit()  # dataRevision
    assert parts[6] == "v1"  # embeddingVersion
    assert parts[7] == "v1"  # indexVersion
    assert len(parts[8]) == 64  # sha256


def test_second_equivalent_search_is_cache_hit(auth_client_a, company_a):
    tender = Tender.objects.create(
        company=company_a,
        title="Edital Cache Test",
        status="PROCESSED",
    )
    DocumentChunk.objects.create(
        company=company_a,
        tender=tender,
        generation=1,
        chunk_index=0,
        page_number=1,
        start_char_offset=0,
        end_char_offset=30,
        text="Fornecimento de computadores",
        text_hash="hash_pc",
        embedding=make_embedding(0.9),
        is_current=True,
        staged=False,
    )

    payload = {"query": "computadores", "topK": 5}

    # Primeira busca: Cache Miss
    res1 = auth_client_a.post("/api/search/semantic/", payload, format="json")
    assert res1.status_code == 200
    data1 = res1.json()
    assert len(data1["data"]) == 1

    # Segunda busca: Cache Hit (repositório NÃO deve ser chamado)
    with patch("apps.intelligence.views.VectorSearchRepository.search") as mock_search:
        res2 = auth_client_a.post("/api/search/semantic/", payload, format="json")
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2 == data1
        # Repositório não foi invocado na segunda requisição
        mock_search.assert_not_called()


def test_cache_does_not_cross_tenants(auth_client_a, auth_client_b, company_a, company_b):
    tender_a = Tender.objects.create(
        company=company_a,
        title="Edital Alpha",
        status="PROCESSED",
    )
    DocumentChunk.objects.create(
        company=company_a,
        tender=tender_a,
        generation=1,
        chunk_index=0,
        page_number=1,
        start_char_offset=0,
        end_char_offset=30,
        text="Alpha dados secretos",
        text_hash="hash_a",
        embedding=make_embedding(0.8),
        is_current=True,
        staged=False,
    )

    payload = {"query": "dados secretos"}

    # Tenant A faz busca (cria cache para tenant A)
    res_a = auth_client_a.post("/api/search/semantic/", payload, format="json")
    assert res_a.status_code == 200
    assert len(res_a.json()["data"]) == 1
    assert "Alpha" in res_a.json()["data"][0]["text"]

    # Tenant B faz a mesma busca (não deve ter acesso ao cache do Tenant A)
    res_b = auth_client_b.post("/api/search/semantic/", payload, format="json")
    assert res_b.status_code == 200
    assert len(res_b.json()["data"]) == 0


def test_data_revision_increment_invalidates_cache(auth_client_a, company_a):
    tender = Tender.objects.create(
        company=company_a,
        title="Edital Invalidation",
        status="PROCESSED",
    )
    DocumentChunk.objects.create(
        company=company_a,
        tender=tender,
        generation=1,
        chunk_index=0,
        page_number=1,
        start_char_offset=0,
        end_char_offset=30,
        text="Texto de teste para invalidacao",
        text_hash="hash_inv",
        embedding=make_embedding(0.7),
        is_current=True,
        staged=False,
    )

    payload = {"query": "invalidacao"}

    # 1. Primeira busca populates cache
    res1 = auth_client_a.post("/api/search/semantic/", payload, format="json")
    assert res1.status_code == 200

    # 2. Incrementa revisão de dados do tenant
    increment_company_data_revision(company_a.id)

    # 3. Segunda busca deve ser Cache Miss (chama repositório novamente)
    with patch(
        "apps.intelligence.views.VectorSearchRepository.search",
        wraps=VectorSearchRepository().search,
    ) as mock_search:
        res2 = auth_client_a.post("/api/search/semantic/", payload, format="json")
        assert res2.status_code == 200
        mock_search.assert_called_once()


def test_search_cache_ttl_is_configurable(auth_client_a, company_a, settings):
    settings.SEARCH_CACHE_TTL = 600
    with patch("apps.intelligence.views.set_search_cache") as mock_set_cache:
        res = auth_client_a.post(
            "/api/search/semantic/", {"query": "configuravel"}, format="json"
        )
        assert res.status_code == 200
        mock_set_cache.assert_called_once()
        # Primeiro argumento é cache_key, segundo é response_data
        call_args = mock_set_cache.call_args
        assert "govintel:v1:semantic:" in call_args[0][0]

