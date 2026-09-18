import pytest
from rest_framework.test import APIClient

from apps.core.jwt_utils import get_tokens_for_user
from apps.core.models import Company, User
from apps.pipeline.models import DocumentChunk
from apps.tenders.models import Tender

pytestmark = pytest.mark.django_db


@pytest.fixture
def company_a():
    return Company.objects.create(name="Empresa Alpha")


@pytest.fixture
def company_b():
    return Company.objects.create(name="Empresa Beta")


@pytest.fixture
def user_a(company_a):
    return User.objects.create_user(
        email="alpha@test.com",
        password="Password123!",
        company=company_a,
    )


@pytest.fixture
def user_b(company_b):
    return User.objects.create_user(
        email="beta@test.com",
        password="Password123!",
        company=company_b,
    )


@pytest.fixture
def auth_client_a(user_a):
    client = APIClient()
    tokens = get_tokens_for_user(user_a)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


def make_embedding(seed_val: float = 0.1, dim: int = 768) -> list[float]:
    vec = [0.0] * dim
    vec[0] = seed_val
    vec[1] = 1.0 - seed_val
    return vec


def test_search_requires_authentication():
    client = APIClient()
    res = client.post("/api/search/semantic/", {"query": "licitação"}, format="json")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "AUTHENTICATION_FAILED"


def test_search_validates_query(auth_client_a):
    # Query ausente
    res = auth_client_a.post("/api/search/semantic/", {}, format="json")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"

    # Query vazia
    res = auth_client_a.post("/api/search/semantic/", {"query": "   "}, format="json")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_search_validates_limits(auth_client_a):
    # topK > 50
    res = auth_client_a.post(
        "/api/search/semantic/", {"query": "teste", "topK": 51}, format="json"
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"

    # topK < 1
    res = auth_client_a.post(
        "/api/search/semantic/", {"query": "teste", "topK": 0}, format="json"
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"

    # pageSize > 50
    res = auth_client_a.post(
        "/api/search/semantic/", {"query": "teste", "pageSize": 51}, format="json"
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"

    # page < 1
    res = auth_client_a.post(
        "/api/search/semantic/", {"query": "teste", "page": 0}, format="json"
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_search_validates_tender_id(auth_client_a, company_b):
    # UUID inválido
    res = auth_client_a.post(
        "/api/search/semantic/", {"query": "teste", "tenderId": "nao-uuid"}, format="json"
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"

    # Tender de outro tenant
    foreign_tender = Tender.objects.create(company=company_b, title="Edital Alheio")
    res = auth_client_a.post(
        "/api/search/semantic/",
        {"query": "teste", "tenderId": str(foreign_tender.id)},
        format="json",
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


def test_search_success_with_score_page_and_snippet(auth_client_a, company_a):
    tender = Tender.objects.create(
        company=company_a,
        title="Edital de Medicamentos 2026",
        status="PROCESSED",
    )
    chunk = DocumentChunk.objects.create(
        company=company_a,
        tender=tender,
        generation=1,
        chunk_index=0,
        page_number=3,
        start_char_offset=100,
        end_char_offset=350,
        text="Item 1: Fornecimento de amoxicilina 500mg com prazo de entrega de 15 dias.",
        text_hash="hash_med",
        embedding=make_embedding(0.8),
        is_current=True,
        staged=False,
    )

    res = auth_client_a.post(
        "/api/search/semantic/",
        {"query": "amoxicilina prazo entrega", "tenderId": str(tender.id)},
        format="json",
    )
    assert res.status_code == 200
    data = res.json()
    assert "data" in data
    assert "pagination" in data
    assert len(data["data"]) == 1

    item = data["data"][0]
    assert item["chunkId"] == str(chunk.id)
    assert item["tenderId"] == str(tender.id)
    assert item["pageNumber"] == 3
    assert item["startCharOffset"] == 100
    assert item["endCharOffset"] == 350
    assert "amoxicilina" in item["text"]
    assert "amoxicilina" in item["snippet"]
    assert isinstance(item["score"], float)
    assert item["score"] > 0.0

    pagination = data["pagination"]
    assert pagination["page"] == 1
    assert pagination["pageSize"] == 20
    assert pagination["totalItems"] == 1
    assert pagination["totalPages"] == 1


def test_search_reranks_mock_vectors_using_terms_in_chunk(auth_client_a, company_a):
    """A busca local deve continuar útil quando o provider semântico é mockado."""
    from apps.intelligence.embeddings import MockEmbeddingAdapter

    tender = Tender.objects.create(
        company=company_a,
        title="Edital de Equipamentos",
        status="PROCESSED",
    )
    adapter = MockEmbeddingAdapter()
    relevant_text = (
        "O prazo de entrega dos equipamentos será de 30 dias corridos "
        "após a emissão da ordem de fornecimento."
    )
    distractor_text = (
        "O objeto da contratação é a prestação de serviços de manutenção "
        "preventiva nas instalações da administração."
    )
    for index, text in enumerate((relevant_text, distractor_text)):
        DocumentChunk.objects.create(
            company=company_a,
            tender=tender,
            generation=1,
            chunk_index=index,
            page_number=index + 1,
            start_char_offset=0,
            end_char_offset=len(text),
            text=text,
            text_hash=f"hash_relevance_{index}",
            embedding=adapter.embed_document(tender.title, text),
            is_current=True,
            staged=False,
        )

    res = auth_client_a.post(
        "/api/search/semantic/",
        {
            "query": "Qual o prazo de entrega dos equipamentos?",
            "tenderId": str(tender.id),
            "topK": 2,
        },
        format="json",
    )

    assert res.status_code == 200
    results = res.json()["data"]
    assert results[0]["text"] == relevant_text
    assert "prazo de entrega" in results[0]["snippet"].lower()


def test_search_strict_cross_tenant_isolation(auth_client_a, company_a, company_b):
    tender_a = Tender.objects.create(company=company_a, title="Edital Alpha", status="PROCESSED")
    tender_b = Tender.objects.create(company=company_b, title="Edital Beta", status="PROCESSED")

    vec = make_embedding(0.9)
    DocumentChunk.objects.create(
        company=company_a,
        tender=tender_a,
        generation=1,
        chunk_index=0,
        page_number=1,
        start_char_offset=0,
        end_char_offset=50,
        text="Dados confidenciais Empresa Alpha",
        text_hash="hash_a",
        embedding=vec,
        is_current=True,
        staged=False,
    )
    DocumentChunk.objects.create(
        company=company_b,
        tender=tender_b,
        generation=1,
        chunk_index=0,
        page_number=1,
        start_char_offset=0,
        end_char_offset=50,
        text="Dados confidenciais Empresa Beta",
        text_hash="hash_b",
        embedding=vec,
        is_current=True,
        staged=False,
    )

    res = auth_client_a.post(
        "/api/search/semantic/",
        {"query": "dados confidenciais"},
        format="json",
    )
    assert res.status_code == 200
    results = res.json()["data"]
    assert len(results) == 1
    assert "Empresa Alpha" in results[0]["text"]
    assert "Empresa Beta" not in results[0]["text"]


def test_search_pagination(auth_client_a, company_a):
    tender = Tender.objects.create(company=company_a, title="Edital Paginacao", status="PROCESSED")
    for i in range(5):
        DocumentChunk.objects.create(
            company=company_a,
            tender=tender,
            generation=1,
            chunk_index=i,
            page_number=i + 1,
            start_char_offset=0,
            end_char_offset=30,
            text=f"Chunk numero {i} do edital de paginacao",
            text_hash=f"hash_{i}",
            embedding=make_embedding(0.1 * (i + 1)),
            is_current=True,
            staged=False,
        )

    # Pagina 1 com pageSize 2
    res_p1 = auth_client_a.post(
        "/api/search/semantic/",
        {"query": "chunk", "topK": 5, "page": 1, "pageSize": 2},
        format="json",
    )
    assert res_p1.status_code == 200
    data_p1 = res_p1.json()
    assert len(data_p1["data"]) == 2
    assert data_p1["pagination"]["page"] == 1
    assert data_p1["pagination"]["pageSize"] == 2
    assert data_p1["pagination"]["totalItems"] == 5
    assert data_p1["pagination"]["totalPages"] == 3

    # Pagina 2 com pageSize 2
    res_p2 = auth_client_a.post(
        "/api/search/semantic/",
        {"query": "chunk", "topK": 5, "page": 2, "pageSize": 2},
        format="json",
    )
    assert res_p2.status_code == 200
    data_p2 = res_p2.json()
    assert len(data_p2["data"]) == 2
    assert data_p2["pagination"]["page"] == 2

    # Pagina 3 com pageSize 2 (deve ter 1 item)
    res_p3 = auth_client_a.post(
        "/api/search/semantic/",
        {"query": "chunk", "topK": 5, "page": 3, "pageSize": 2},
        format="json",
    )
    assert res_p3.status_code == 200
    data_p3 = res_p3.json()
    assert len(data_p3["data"]) == 1
    assert data_p3["pagination"]["page"] == 3


def test_search_empty_tenant(auth_client_a):
    res = auth_client_a.post(
        "/api/search/semantic/",
        {"query": "qualquer termo"},
        format="json",
    )
    assert res.status_code == 200
    data = res.json()
    assert data["data"] == []
    assert data["pagination"]["totalItems"] == 0
    assert data["pagination"]["totalPages"] == 0
