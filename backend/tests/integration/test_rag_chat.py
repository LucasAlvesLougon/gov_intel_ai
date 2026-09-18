import pytest
from rest_framework.test import APIClient

from apps.conversations.models import Conversation, Message
from apps.core.jwt_utils import get_tokens_for_user
from apps.core.models import Company, User
from apps.pipeline.models import DocumentChunk
from apps.tenders.models import Tender

pytestmark = pytest.mark.django_db


@pytest.fixture
def company_a():
    return Company.objects.create(name="Empresa RAG Alpha")


@pytest.fixture
def company_b():
    return Company.objects.create(name="Empresa RAG Beta")


@pytest.fixture
def user_a(company_a):
    return User.objects.create_user(
        email="rag_alpha@test.com",
        password="Password123!",
        company=company_a,
    )


@pytest.fixture
def auth_client_a(user_a):
    client = APIClient()
    tokens = get_tokens_for_user(user_a)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


def make_embedding(seed_val: float = 0.5, dim: int = 768) -> list[float]:
    vec = [0.0] * dim
    vec[0] = seed_val
    vec[1] = 1.0 - seed_val
    return vec


def test_chat_requires_authentication():
    client = APIClient()
    import uuid

    res = client.post(f"/api/tenders/{uuid.uuid4()}/chat/", {"message": "Olá"}, format="json")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "AUTHENTICATION_FAILED"


def test_chat_rejects_non_processed_tender(auth_client_a, company_a):
    tender = Tender.objects.create(
        company=company_a,
        title="Edital em Processamento",
        status="PROCESSING",
    )
    res = auth_client_a.post(
        f"/api/tenders/{tender.id}/chat/",
        {"message": "Qual o valor estimado?"},
        format="json",
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "CONFLICT"


def test_chat_rejects_cross_tenant_tender(auth_client_a, company_b):
    tender_b = Tender.objects.create(
        company=company_b,
        title="Edital Tenant Beta",
        status="PROCESSED",
    )
    res = auth_client_a.post(
        f"/api/tenders/{tender_b.id}/chat/",
        {"message": "Qual o prazo?"},
        format="json",
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


def test_chat_validates_message_payload(auth_client_a, company_a):
    tender = Tender.objects.create(
        company=company_a,
        title="Edital Validação",
        status="PROCESSED",
    )
    # Mensagem vazia
    res = auth_client_a.post(
        f"/api/tenders/{tender.id}/chat/",
        {"message": "   "},
        format="json",
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"

    # Mensagem ausente
    res = auth_client_a.post(
        f"/api/tenders/{tender.id}/chat/",
        {},
        format="json",
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_chat_validates_conversation_id(auth_client_a, company_a, company_b):
    tender = Tender.objects.create(
        company=company_a,
        title="Edital Valida Conv",
        status="PROCESSED",
    )

    # UUID inválido
    res = auth_client_a.post(
        f"/api/tenders/{tender.id}/chat/",
        {"message": "Teste", "conversationId": "invalido"},
        format="json",
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"

    # Conversa inexistente ou de outro tenant
    import uuid

    res = auth_client_a.post(
        f"/api/tenders/{tender.id}/chat/",
        {"message": "Teste", "conversationId": str(uuid.uuid4())},
        format="json",
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


def test_chat_auto_creates_conversation_when_omitted(auth_client_a, company_a):
    tender = Tender.objects.create(
        company=company_a,
        title="Edital Auto Conv",
        status="PROCESSED",
    )
    DocumentChunk.objects.create(
        company=company_a,
        tender=tender,
        generation=1,
        chunk_index=0,
        page_number=1,
        start_char_offset=0,
        end_char_offset=40,
        text="Objeto: Contratacao de servicos de TI.",
        text_hash="hash_ti",
        embedding=make_embedding(0.9),
        is_current=True,
        staged=False,
    )

    res = auth_client_a.post(
        f"/api/tenders/{tender.id}/chat/",
        {"message": "Qual o objeto da contratacao?"},
        format="json",
    )
    assert res.status_code == 200
    data = res.json()
    assert "conversationId" in data
    assert "message" in data

    conv_id = data["conversationId"]
    conv = Conversation.objects.filter(id=conv_id).first()
    assert conv is not None
    assert conv.tender == tender
    assert conv.company == company_a

    # Mensagens persistidas: 1 do usuário, 1 do assistente
    msgs = Message.objects.filter(conversation=conv).order_by("created_at")
    assert msgs.count() == 2
    assert msgs[0].role == "user"
    assert msgs[0].content == "Qual o objeto da contratacao?"
    assert msgs[1].role == "assistant"


def test_chat_returns_grounded_answer_with_verifiable_citations(auth_client_a, company_a):
    tender = Tender.objects.create(
        company=company_a,
        title="Edital Medicamentos Grounding",
        status="PROCESSED",
    )
    chunk = DocumentChunk.objects.create(
        company=company_a,
        tender=tender,
        generation=1,
        chunk_index=0,
        page_number=4,
        start_char_offset=50,
        end_char_offset=120,
        text="O prazo de entrega sera de 10 dias corridos apos a solicitacao.",
        text_hash="hash_prazo",
        embedding=make_embedding(0.85),
        is_current=True,
        staged=False,
    )

    res = auth_client_a.post(
        f"/api/tenders/{tender.id}/chat/",
        {"message": "Qual o prazo de entrega?"},
        format="json",
    )
    assert res.status_code == 200
    data = res.json()
    msg = data["message"]
    assert msg["role"] == "assistant"
    assert len(msg["citations"]) >= 1

    citation = msg["citations"][0]
    assert citation["chunkId"] == str(chunk.id)
    assert citation["pageNumber"] == 4
    assert "prazo de entrega" in citation["quote"]
    assert "text" not in citation
    assert "score" in citation
    assert citation["score"] > 0


def test_mock_rag_returns_matching_sentence_instead_of_full_chunk(company_a):
    from apps.conversations.rag_service import MockRAGService

    relevant = (
        "O prazo de entrega é de 30 dias corridos. "
        "A contratada também deverá manter a regularidade fiscal durante a execução."
    )
    retrieved = [
        {
            "chunkId": "11111111-1111-1111-1111-111111111111",
            "pageNumber": 2,
            "text": relevant,
            "snippet": relevant[:200],
            "score": 0.92,
        }
    ]

    result = MockRAGService().answer(
        company=company_a,
        tender=None,
        user_query="Qual é o prazo de entrega?",
        retrieved_chunks=retrieved,
    )

    assert "30 dias corridos" in result["answer"]
    assert "regularidade fiscal" not in result["answer"]
    assert result["citations"][0]["quote"] == "O prazo de entrega é de 30 dias corridos."


def test_mock_rag_does_not_answer_from_a_weak_unrelated_match(company_a):
    from apps.conversations.rag_service import MockRAGService

    result = MockRAGService().answer(
        company=company_a,
        tender=None,
        user_query="Qual é a fórmula molecular da substância X?",
        retrieved_chunks=[
            {
                "chunkId": "11111111-1111-1111-1111-111111111111",
                "pageNumber": 1,
                "text": "O fornecedor deverá entregar os equipamentos em 30 dias.",
                "snippet": "O fornecedor deverá entregar os equipamentos em 30 dias.",
                "score": 0.25,
            }
        ],
    )

    assert result["citations"] == []
    assert "evidências suficientes" in result["answer"]


def test_chat_declares_insufficiency_when_no_evidence(auth_client_a, company_a):
    tender = Tender.objects.create(
        company=company_a,
        title="Edital Limpeza",
        status="PROCESSED",
    )
    # Sem chunks cadastrados ou chunks completamente não relacionados
    res = auth_client_a.post(
        f"/api/tenders/{tender.id}/chat/",
        {"message": "Qual a formula molecular da substancia X?"},
        format="json",
    )
    assert res.status_code == 200
    data = res.json()
    msg = data["message"]
    content_lower = msg["content"].lower()
    assert "insuficiente" in content_lower or "não foram encontradas" in content_lower
    assert msg["citations"] == []


def test_chat_appends_to_existing_conversation(auth_client_a, company_a, user_a):
    tender = Tender.objects.create(
        company=company_a,
        title="Edital Conversa Continua",
        status="PROCESSED",
    )
    conv = Conversation.objects.create(
        company=company_a,
        user=user_a,
        tender=tender,
        title="Duvidas Edital",
    )

    res1 = auth_client_a.post(
        f"/api/tenders/{tender.id}/chat/",
        {"message": "Primeira pergunta", "conversationId": str(conv.id)},
        format="json",
    )
    assert res1.status_code == 200
    assert res1.json()["conversationId"] == str(conv.id)

    res2 = auth_client_a.post(
        f"/api/tenders/{tender.id}/chat/",
        {"message": "Segunda pergunta", "conversationId": str(conv.id)},
        format="json",
    )
    assert res2.status_code == 200
    assert res2.json()["conversationId"] == str(conv.id)

    # Deve conter 4 mensagens (2 pares user/assistant)
    assert conv.messages.count() == 4


def test_validate_citations_rejects_hallucinated_ids_and_divergent_quotes():
    from apps.conversations.rag_service import validate_citations

    retrieved = [
        {
            "chunkId": "11111111-1111-1111-1111-111111111111",
            "pageNumber": 2,
            "text": "O fornecedor deve entregar as mercadorias em ate trinta dias.",
            "score": 0.91,
        }
    ]

    raw_citations = [
        # Citação válida existente
        {
            "chunkId": "11111111-1111-1111-1111-111111111111",
            "quote": "O fornecedor deve entregar as mercadorias",
        },
        # Citação com ID alucinado (não está no retrieval)
        {
            "chunkId": "99999999-9999-9999-9999-999999999999",
            "quote": "Texto inventado",
        },
        # Citação válida mas com quote que não existe no chunk
        {
            "chunkId": "11111111-1111-1111-1111-111111111111",
            "quote": "Frase que nao existe no chunk original",
        },
    ]

    validated = validate_citations(raw_citations, retrieved)

    # O ID alucinado e o quote divergente são descartados em modo fail-closed.
    assert len(validated) == 1
    assert all(c["chunkId"] == "11111111-1111-1111-1111-111111111111" for c in validated)
    assert all("text" not in c for c in validated)
    assert validated[0]["quote"] == "O fornecedor deve entregar as mercadorias"


def test_invalid_only_citation_returns_insufficient_evidence(auth_client_a, company_a):
    from apps.conversations.rag_service import OpenRouterRAGService

    retrieved = [
        {
            "chunkId": "11111111-1111-1111-1111-111111111111",
            "pageNumber": 1,
            "text": "O prazo de entrega é de 30 dias.",
            "score": 0.9,
        }
    ]

    class FakeResponse:
            content = (
                '{"answer":"Resposta sem prova", "citations":['
                '{"chunkId":"11111111-1111-1111-1111-111111111111",'
                '"quote":"texto inventado"}]}'
            )

    class FakeLLM:
        def __init__(self, **kwargs):
            pass

        def invoke(self, messages):
            return FakeResponse()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("apps.conversations.rag_service.ChatOpenAI", FakeLLM)
        result = OpenRouterRAGService(api_key="test-key").answer(
            company=company_a,
            tender=None,
            user_query="Qual o prazo?",
            retrieved_chunks=retrieved,
        )

    assert result["answer"] == (
        "Não foram encontradas evidências suficientes no edital para responder a esta pergunta."
    )
    assert result["citations"] == []


def test_openrouter_retries_when_citations_are_not_literal(monkeypatch, company_a):
    import json as jsonlib
    from types import SimpleNamespace

    from apps.conversations.rag_service import OpenRouterRAGService

    class FakeLLM:
        calls = 0

        def __init__(self, **kwargs):
            pass

        def invoke(self, messages):
            type(self).calls += 1
            quote = (
                "texto inventado"
                if type(self).calls == 1
                else "trecho exato do chunk"
            )
            return SimpleNamespace(
                content=jsonlib.dumps(
                    {
                        "answer": "RESPOSTA COM PROVA",
                        "citations": [
                            {
                                "chunkId": "11111111-1111-1111-1111-111111111111",
                                "quote": quote,
                            }
                        ],
                    }
                )
            )

    monkeypatch.setattr("apps.conversations.rag_service.ChatOpenAI", FakeLLM)
    retrieved = [
        {
            "chunkId": "11111111-1111-1111-1111-111111111111",
            "pageNumber": 1,
            "text": "trecho exato do chunk",
            "score": 0.9,
        }
    ]

    result = OpenRouterRAGService(api_key="test-key").answer(
        company=company_a,
        tender=None,
        user_query="Qual o prazo?",
        retrieved_chunks=retrieved,
    )

    assert FakeLLM.calls == 2
    assert result["answer"] == "RESPOSTA COM PROVA"
    assert result["citations"][0]["quote"] == "trecho exato do chunk"


def test_langchain_rag_prompts_for_complete_answers(monkeypatch, company_a):
    import json as jsonlib
    from types import SimpleNamespace

    from apps.conversations.rag_service import LangChainRAGService

    captured = {}

    class FakeModels:
        def generate_content(self, model, contents, config):
            captured["model"] = model
            captured["contents"] = contents
            captured["config"] = config
            return SimpleNamespace(
                text=jsonlib.dumps(
                    {
                        "answer": "RESPOSTA COMPLETA DO GEMINI",
                        "citations": [
                            {
                                "chunkId": "11111111-1111-1111-1111-111111111111",
                                "quote": "trecho exato do chunk",
                            }
                        ],
                    }
                )
            )

    class FakeClient:
        def __init__(self, api_key=None):
            self.models = FakeModels()

    monkeypatch.setattr("google.genai.Client", FakeClient)

    retrieved = [
        {
            "chunkId": "11111111-1111-1111-1111-111111111111",
            "pageNumber": 2,
            "text": "trecho exato do chunk",
            "score": 0.9,
        }
    ]

    result = LangChainRAGService(api_key="chave-teste").answer(
        company=company_a,
        tender=None,
        user_query="Liste todos os prazos do edital.",
        retrieved_chunks=retrieved,
    )

    system_instruction = captured["config"]["system_instruction"]
    assert "COMPLETA" in system_instruction
    assert "todos" in system_instruction
    assert result["answer"] == "RESPOSTA COMPLETA DO GEMINI"
    assert result["citations"][0]["quote"] == "trecho exato do chunk"
    assert "text" not in result["citations"][0]


def test_process_rag_chat_retrieves_spec_default_top_k(monkeypatch, company_a, user_a):
    from apps.conversations import rag_service
    from apps.conversations.rag_service import process_rag_chat

    recorded = {}

    class FakeRepo:
        def search(self, company, query_vector, tender_id=None, top_k=8, query_text=None):
            recorded["top_k"] = top_k
            return []

    monkeypatch.setattr(rag_service, "VectorSearchRepository", FakeRepo)

    tender = Tender.objects.create(
        company=company_a,
        title="Edital TopK",
        status="PROCESSED",
    )
    conv = Conversation.objects.create(company=company_a, user=user_a, tender=tender)

    result = process_rag_chat(company_a, tender, conv, "Qual o prazo?")

    assert recorded["top_k"] == rag_service.CHAT_RETRIEVAL_TOP_K
    assert rag_service.CHAT_RETRIEVAL_TOP_K == 8
    content_lower = result["message"].content.lower()
    assert "insuficiente" in content_lower or "não foram encontradas" in content_lower


def test_openrouter_rag_service_uses_mimo_via_openrouter(monkeypatch, company_a):
    import json as jsonlib
    from types import SimpleNamespace

    from apps.conversations.rag_service import OpenRouterRAGService

    captured = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured["init"] = kwargs

        def invoke(self, messages):
            captured["messages"] = messages
            return SimpleNamespace(
                content=jsonlib.dumps(
                    {
                        "answer": "RESPOSTA DO MIMO",
                        "citations": [
                            {
                                "chunkId": "11111111-1111-1111-1111-111111111111",
                                "quote": "trecho exato do chunk",
                            }
                        ],
                    }
                )
            )

    monkeypatch.setattr("apps.conversations.rag_service.ChatOpenAI", FakeChatOpenAI)

    retrieved = [
        {
            "chunkId": "11111111-1111-1111-1111-111111111111",
            "pageNumber": 2,
            "text": "trecho exato do chunk",
            "score": 0.9,
        }
    ]

    result = OpenRouterRAGService(api_key="or-key").answer(
        company=company_a,
        tender=None,
        user_query="Liste todos os prazos do edital.",
        retrieved_chunks=retrieved,
    )

    init = captured["init"]
    assert init["model"] == "xiaomi/mimo-v2.5"
    assert init["base_url"] == "https://openrouter.ai/api/v1"
    assert init["api_key"] == "or-key"

    assert len(captured["messages"]) == 2
    assert "COMPLETA" in captured["messages"][0].content
    assert "Liste todos os prazos" in captured["messages"][1].content

    assert result["answer"] == "RESPOSTA DO MIMO"
    assert result["citations"][0]["quote"] == "trecho exato do chunk"
    assert "text" not in result["citations"][0]


def test_get_rag_service_prefers_openrouter(monkeypatch):
    from apps.conversations.rag_service import (
        LangChainRAGService,
        OpenRouterRAGService,
        get_rag_service,
    )

    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    assert isinstance(get_rag_service(), OpenRouterRAGService)

    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    assert isinstance(get_rag_service(), LangChainRAGService)

    monkeypatch.setenv("LLM_PROVIDER", "mock")
    from apps.conversations.rag_service import MockRAGService

    assert isinstance(get_rag_service(), MockRAGService)


def test_mock_quote_never_truncated_mid_sentence(company_a):
    from apps.conversations.rag_service import MockRAGService

    # Duas frases relevantes (mesma sobreposição máxima) somando mais de 600 chars
    s1 = (
        "A contratada deverá apresentar a relação completa de documentos exigidos "
        "para a execução do objeto, incluindo atestados, certidões e declarações "
        "que comprovem a regularidade técnica e jurídica da proposta apresentada."
    )
    s2 = (
        "O gestor do contrato deverá acompanhar mensalmente a evolução dos serviços "
        "prestados, lavrando termo de ocorrências sempre que constatadas falhas "
        "relevantes no desempenho, sob pena de aplicação das sanções cabíveis."
    )
    retrieved = [
        {
            "chunkId": "11111111-1111-1111-1111-111111111111",
            "pageNumber": 1,
            "text": f"{s1} {s2}",
            "snippet": f"{s1} {s2}"[:200],
            "score": 0.95,
        }
    ]

    result = MockRAGService().answer(
        company=company_a,
        tender=None,
        user_query="documentos exigidos",
        retrieved_chunks=retrieved,
    )

    quote = result["citations"][0]["quote"]
    assert len(quote) <= 600
    assert quote.endswith(".")
    assert quote.startswith(s1[:30])


def test_rag_fallback_logs_warning_when_provider_fails(monkeypatch, company_a, caplog):
    import logging as logging_module

    from apps.conversations.rag_service import LangChainRAGService

    def boom(*args, **kwargs):
        raise RuntimeError("falha simulada do provedor")

    monkeypatch.setattr("google.genai.Client", boom)

    with caplog.at_level(logging_module.WARNING):
        result = LangChainRAGService(api_key="chave-teste").answer(
            company=company_a,
            tender=None,
            user_query="Qual o prazo?",
            retrieved_chunks=[
                {
                    "chunkId": "11111111-1111-1111-1111-111111111111",
                    "pageNumber": 1,
                    "text": "Texto de exemplo qualquer para fallback.",
                    "score": 0.9,
                }
            ],
        )

    assert "evidências suficientes" in result["answer"] or result["answer"]
    assert any("fallback" in record.message.lower() for record in caplog.records)
