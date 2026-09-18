import pytest

from apps.core.models import Company
from apps.intelligence.repository import VectorSearchRepository
from apps.pipeline.models import DocumentChunk
from apps.tenders.models import Tender

pytestmark = pytest.mark.django_db


def make_embedding(value: float = 0.1, dim: int = 768) -> list[float]:
    vec = [0.0] * dim
    vec[0] = value
    return vec


def test_document_chunk_has_vector_and_metadata_fields():
    company = Company.objects.create(name="Vector Test Corp")
    tender = Tender.objects.create(company=company, title="Edital Vetorial")
    vector = make_embedding(0.5)

    chunk = DocumentChunk.objects.create(
        company=company,
        tender=tender,
        generation=1,
        chunk_index=0,
        page_number=1,
        start_char_offset=0,
        end_char_offset=50,
        text="Texto de teste para pgvector",
        text_hash="hash0",
        embedding=vector,
        embedding_model_name="gemini-embedding-2",
        embedding_dimensions=768,
        normalization="NFKC",
        preprocessing_fingerprint="v1-clean-whitespace",
        is_current=True,
        staged=False,
    )

    chunk.refresh_from_db()
    assert chunk.embedding is not None
    assert len(chunk.embedding) == 768
    assert chunk.embedding_dimensions == 768
    assert chunk.embedding_model_name == "gemini-embedding-2"


def test_search_filters_strictly_by_tenant():
    company_a = Company.objects.create(name="Tenant A")
    company_b = Company.objects.create(name="Tenant B")

    tender_a = Tender.objects.create(company=company_a, title="Edital A")
    tender_b = Tender.objects.create(company=company_b, title="Edital B")

    vec = make_embedding(0.9)

    DocumentChunk.objects.create(
        company=company_a,
        tender=tender_a,
        generation=1,
        chunk_index=0,
        page_number=1,
        start_char_offset=0,
        end_char_offset=20,
        text="Documento exclusivo Tenant A",
        text_hash="hashA",
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
        end_char_offset=20,
        text="Documento confidencial Tenant B",
        text_hash="hashB",
        embedding=vec,
        is_current=True,
        staged=False,
    )

    repo = VectorSearchRepository()
    results_a = repo.search(company=company_a, query_vector=vec, top_k=5)

    assert len(results_a) == 1
    assert results_a[0]["chunkId"] is not None
    assert "Tenant A" in results_a[0]["text"]
    assert "Tenant B" not in results_a[0]["text"]


def test_search_filters_chunks_from_other_embedding_provider():
    company = Company.objects.create(name="Provider Isolation Corp")
    tender = Tender.objects.create(company=company, title="Edital Provider")
    vec = make_embedding(0.9)

    DocumentChunk.objects.create(
        company=company,
        tender=tender,
        generation=1,
        chunk_index=0,
        page_number=1,
        start_char_offset=0,
        end_char_offset=20,
        text="Chunk do provider ativo",
        text_hash="active-provider",
        embedding=vec,
        embedding_provider="mock",
        is_current=True,
        staged=False,
    )
    DocumentChunk.objects.create(
        company=company,
        tender=tender,
        generation=1,
        chunk_index=1,
        page_number=1,
        start_char_offset=20,
        end_char_offset=45,
        text="Chunk de provider incompatível",
        text_hash="other-provider",
        embedding=vec,
        embedding_provider="openrouter",
        is_current=True,
        staged=False,
    )

    results = VectorSearchRepository().search(company=company, query_vector=vec, top_k=5)

    assert [item["text"] for item in results] == ["Chunk do provider ativo"]


def test_search_ignores_staged_and_non_current_chunks():
    company = Company.objects.create(name="Staged Test Corp")
    tender = Tender.objects.create(company=company, title="Edital Staged")
    vec = make_embedding(0.8)

    # Chunk corrente
    DocumentChunk.objects.create(
        company=company,
        tender=tender,
        generation=1,
        chunk_index=0,
        page_number=1,
        start_char_offset=0,
        end_char_offset=20,
        text="Chunk corrente visivel",
        text_hash="curr",
        embedding=vec,
        is_current=True,
        staged=False,
    )

    # Chunk staged (geração futura em processamento)
    DocumentChunk.objects.create(
        company=company,
        tender=tender,
        generation=2,
        chunk_index=0,
        page_number=1,
        start_char_offset=0,
        end_char_offset=20,
        text="Chunk staged invisivel",
        text_hash="staged",
        embedding=vec,
        is_current=False,
        staged=True,
    )

    repo = VectorSearchRepository()
    results = repo.search(company=company, query_vector=vec, top_k=5)

    assert len(results) == 1
    assert results[0]["text"] == "Chunk corrente visivel"


def test_search_orders_by_similarity_and_returns_scores():
    company = Company.objects.create(name="Score Test Corp")
    tender = Tender.objects.create(company=company, title="Edital Score")

    # query vector along dimension 0
    query_vec = [0.0] * 768
    query_vec[0] = 1.0

    # close vector: mostly along dimension 0
    close_vec = [0.0] * 768
    close_vec[0] = 0.9
    close_vec[1] = 0.1

    # far vector: orthogonal along dimension 1
    far_vec = [0.0] * 768
    far_vec[1] = 1.0

    DocumentChunk.objects.create(
        company=company,
        tender=tender,
        generation=1,
        chunk_index=0,
        page_number=1,
        start_char_offset=0,
        end_char_offset=30,
        text="Resultado Muito Proximo",
        text_hash="close",
        embedding=close_vec,
        is_current=True,
        staged=False,
    )

    DocumentChunk.objects.create(
        company=company,
        tender=tender,
        generation=1,
        chunk_index=1,
        page_number=2,
        start_char_offset=30,
        end_char_offset=60,
        text="Resultado Distante",
        text_hash="far",
        embedding=far_vec,
        is_current=True,
        staged=False,
    )

    repo = VectorSearchRepository()
    results = repo.search(company=company, query_vector=query_vec, top_k=5)

    assert len(results) == 2
    assert results[0]["text"] == "Resultado Muito Proximo"
    assert results[0]["score"] > results[1]["score"]
    assert results[0]["pageNumber"] == 1
    assert results[0]["startCharOffset"] == 0


def test_search_with_tender_id_filter():
    company = Company.objects.create(name="Tender Filter Corp")
    tender_1 = Tender.objects.create(company=company, title="Edital 1")
    tender_2 = Tender.objects.create(company=company, title="Edital 2")
    vec = make_embedding(0.5)

    DocumentChunk.objects.create(
        company=company,
        tender=tender_1,
        generation=1,
        chunk_index=0,
        page_number=1,
        start_char_offset=0,
        end_char_offset=20,
        text="Texto Edital 1",
        text_hash="t1",
        embedding=vec,
        is_current=True,
        staged=False,
    )

    DocumentChunk.objects.create(
        company=company,
        tender=tender_2,
        generation=1,
        chunk_index=0,
        page_number=1,
        start_char_offset=0,
        end_char_offset=20,
        text="Texto Edital 2",
        text_hash="t2",
        embedding=vec,
        is_current=True,
        staged=False,
    )

    repo = VectorSearchRepository()
    results = repo.search(company=company, query_vector=vec, tender_id=tender_1.id, top_k=5)

    assert len(results) == 1
    assert results[0]["text"] == "Texto Edital 1"


def test_search_empty_tenant_returns_empty_list():
    empty_company = Company.objects.create(name="Empty Corp")
    vec = make_embedding(0.5)

    repo = VectorSearchRepository()
    results = repo.search(company=empty_company, query_vector=vec, top_k=5)
    assert results == []


def test_search_small_tenant_returns_all_available_chunks():
    company = Company.objects.create(name="Small Tenant Corp")
    tender = Tender.objects.create(company=company, title="Edital Pequeno")

    for i in range(3):
        DocumentChunk.objects.create(
            company=company,
            tender=tender,
            generation=1,
            chunk_index=i,
            page_number=1,
            start_char_offset=i * 20,
            end_char_offset=(i + 1) * 20,
            text=f"Chunk pequeno {i}",
            text_hash=f"small_{i}",
            embedding=make_embedding(0.2 * (i + 1)),
            is_current=True,
            staged=False,
        )

    repo = VectorSearchRepository()
    # top_k maior que quantidade existente (5 > 3)
    results = repo.search(company=company, query_vector=make_embedding(0.2), top_k=5)
    assert len(results) == 3
    assert all("snippet" in r for r in results)


def test_search_biased_tenant_returns_correct_ordering_and_snippets():
    company = Company.objects.create(name="Biased Tenant Corp")
    tender = Tender.objects.create(company=company, title="Edital Enviesado")

    # Criando chunks com vetores em direções distintas
    v_near = [0.0] * 768
    v_near[0] = 0.95
    v_near[1] = 0.05

    v_far = [0.0] * 768
    v_far[1] = 1.0

    long_text = (
        "Trecho com mais de duzentos caracteres para testar se o snippet é gerado "
        "corretamente e truncado sem problemas. " * 3
    )
    DocumentChunk.objects.create(
        company=company,
        tender=tender,
        generation=1,
        chunk_index=0,
        page_number=1,
        start_char_offset=0,
        end_char_offset=len(long_text),
        text=long_text,
        text_hash="long_hash",
        embedding=v_near,
        is_current=True,
        staged=False,
    )
    DocumentChunk.objects.create(
        company=company,
        tender=tender,
        generation=1,
        chunk_index=1,
        page_number=2,
        start_char_offset=0,
        end_char_offset=20,
        text="Trecho curto distante",
        text_hash="short_hash",
        embedding=v_far,
        is_current=True,
        staged=False,
    )

    query_v = [0.0] * 768
    query_v[0] = 1.0

    repo = VectorSearchRepository()
    results = repo.search(company=company, query_vector=query_v, top_k=10)
    assert len(results) == 2
    assert results[0]["score"] > results[1]["score"]
    assert len(results[0]["snippet"]) <= 200
    assert results[0]["pageNumber"] == 1
