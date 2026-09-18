import math
from unittest.mock import MagicMock, patch

import pytest

from apps.intelligence.embeddings import GeminiEmbeddingAdapter


def test_api_key_required(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiEmbeddingAdapter()


def test_embed_document_uses_embedding_2_document_instruction(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key-123")
    mock_vector = [0.1] * 768

    with patch("apps.intelligence.embeddings.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_embedding = MagicMock()
        mock_embedding.values = mock_vector
        mock_response = MagicMock()
        mock_response.embeddings = [mock_embedding]
        mock_client.models.embed_content.return_value = mock_response

        adapter = GeminiEmbeddingAdapter()
        vector = adapter.embed_document(title="Edital Medicamentos", text="Texto de teste")

        assert len(vector) == 768
        assert vector == mock_vector

        # Verifica argumentos passados ao google-genai
        mock_client.models.embed_content.assert_called_once()
        call_kwargs = mock_client.models.embed_content.call_args[1]
        assert call_kwargs["model"] == "gemini-embedding-2"
        assert call_kwargs["contents"] == "title: Edital Medicamentos | text: Texto de teste"
        config = call_kwargs["config"]
        assert not hasattr(config, "task_type") or config.task_type is None
        assert not hasattr(config, "title") or config.title is None
        assert config.output_dimensionality == 768


def test_embed_query_uses_embedding_2_query_instruction(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key-123")
    mock_vector = [0.2] * 768

    with patch("apps.intelligence.embeddings.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_embedding = MagicMock()
        mock_embedding.values = mock_vector
        mock_response = MagicMock()
        mock_response.embeddings = [mock_embedding]
        mock_client.models.embed_content.return_value = mock_response

        adapter = GeminiEmbeddingAdapter()
        vector = adapter.embed_query("qual o prazo de entrega?")

        assert len(vector) == 768
        assert vector == mock_vector

        call_kwargs = mock_client.models.embed_content.call_args[1]
        assert call_kwargs["contents"] == "task: search result | query: qual o prazo de entrega?"
        config = call_kwargs["config"]
        assert not hasattr(config, "task_type") or config.task_type is None
        assert config.output_dimensionality == 768


def test_different_dimension_is_rejected(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key-123")
    # Mock retornando dimensão errada (ex: 512)
    wrong_vector = [0.1] * 512

    with patch("apps.intelligence.embeddings.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_embedding = MagicMock()
        mock_embedding.values = wrong_vector
        mock_response = MagicMock()
        mock_response.embeddings = [mock_embedding]
        mock_client.models.embed_content.return_value = mock_response

        adapter = GeminiEmbeddingAdapter(expected_dimensions=768)
        with pytest.raises(ValueError, match="768"):
            adapter.embed_document(title="Titulo", text="Texto")


def test_embed_documents_batch(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key-123")
    mock_vector = [0.05] * 768

    with patch("apps.intelligence.embeddings.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_embedding = MagicMock()
        mock_embedding.values = mock_vector
        mock_response = MagicMock()
        mock_response.embeddings = [mock_embedding]
        mock_client.models.embed_content.return_value = mock_response

        adapter = GeminiEmbeddingAdapter()
        docs = [("Edital 1", "Chunk 1"), ("Edital 1", "Chunk 2")]
        vectors = adapter.embed_documents_batch(docs)

        assert len(vectors) == 2
        assert len(vectors[0]) == 768
        assert len(vectors[1]) == 768


def test_mock_embedding_adapter_generates_deterministic_768_vectors():
    from apps.intelligence.embeddings import MockEmbeddingAdapter

    mock_adapter = MockEmbeddingAdapter()
    vec1 = mock_adapter.embed_document("Titulo", "Conteudo do edital")
    vec2 = mock_adapter.embed_document("Titulo", "Conteudo do edital")
    vec_diff = mock_adapter.embed_document("Outro", "Conteudo diferente")

    assert len(vec1) == 768
    assert vec1 == vec2
    assert vec1 != vec_diff

    query_vec = mock_adapter.embed_query("pesquisa licitacao")
    assert len(query_vec) == 768

    batch_vecs = mock_adapter.embed_documents_batch([("T1", "C1"), ("T2", "C2")])
    assert len(batch_vecs) == 2
    assert len(batch_vecs[0]) == 768
    assert len(batch_vecs[1]) == 768


def test_get_embedding_adapter_factory(monkeypatch):
    from apps.intelligence.embeddings import (
        GeminiEmbeddingAdapter,
        LocalEmbeddingAdapter,
        get_embedding_adapter,
    )

    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    adapter = get_embedding_adapter()
    assert isinstance(adapter, LocalEmbeddingAdapter)

    monkeypatch.setenv("GEMINI_API_KEY", "mock")
    adapter = get_embedding_adapter()
    assert isinstance(adapter, LocalEmbeddingAdapter)

    monkeypatch.setenv("GEMINI_API_KEY", "actual-secret-key")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    with patch("apps.intelligence.embeddings.genai.Client"):
        adapter = get_embedding_adapter()
        assert isinstance(adapter, GeminiEmbeddingAdapter)


# ---------- OpenRouterEmbeddingAdapter ----------------------------------------

def _fake_openrouter_response(vectors: list[list[float]]):
    from types import SimpleNamespace

    data = [SimpleNamespace(embedding=v, index=i) for i, v in enumerate(vectors)]
    return SimpleNamespace(data=data, model="openai/text-embedding-3-small")


def test_openrouter_embedding_adapter_sends_openai_compatible_payload(monkeypatch):
    from apps.intelligence.embeddings import OpenRouterEmbeddingAdapter

    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key-123")
    vector = [0.1] * 768

    with patch("apps.intelligence.embeddings.OpenAI") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.embeddings.create.return_value = _fake_openrouter_response([vector])

        adapter = OpenRouterEmbeddingAdapter()
        result = adapter.embed_document(title="Edital Medicamentos", text="Texto de teste")

        assert result == vector

        mock_client_cls.assert_called_once()
        client_kwargs = mock_client_cls.call_args[1]
        assert client_kwargs["api_key"] == "or-key-123"
        assert client_kwargs["base_url"] == "https://openrouter.ai/api/v1"

        call_kwargs = mock_client.embeddings.create.call_args[1]
        assert call_kwargs["model"] == "openai/text-embedding-3-small"
        assert call_kwargs["input"] == ["title: Edital Medicamentos | text: Texto de teste"]
        assert call_kwargs["dimensions"] == 768
        assert call_kwargs["extra_body"] == {"input_type": "search_document"}


def test_openrouter_embedding_adapter_query_uses_search_query(monkeypatch):
    from apps.intelligence.embeddings import OpenRouterEmbeddingAdapter

    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key-123")
    vector = [0.2] * 768

    with patch("apps.intelligence.embeddings.OpenAI") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.embeddings.create.return_value = _fake_openrouter_response([vector])

        adapter = OpenRouterEmbeddingAdapter()
        result = adapter.embed_query("qual o prazo de entrega?")

        assert result == vector
        call_kwargs = mock_client.embeddings.create.call_args[1]
        assert call_kwargs["input"] == ["task: search result | query: qual o prazo de entrega?"]
        assert call_kwargs["extra_body"] == {"input_type": "search_query"}


def test_openrouter_adapter_rejects_wrong_dimension(monkeypatch):
    from apps.intelligence.embeddings import OpenRouterEmbeddingAdapter

    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key-123")
    wrong_vector = [0.1] * 512

    with patch("apps.intelligence.embeddings.OpenAI") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.embeddings.create.return_value = _fake_openrouter_response([wrong_vector])

        adapter = OpenRouterEmbeddingAdapter(expected_dimensions=768)
        with pytest.raises(ValueError, match="768"):
            adapter.embed_document(title="Titulo", text="Texto")


def test_openrouter_batch_preserves_input_order(monkeypatch):
    from apps.intelligence.embeddings import OpenRouterEmbeddingAdapter

    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key-123")
    vec_a = [0.01] * 768
    vec_b = [0.02] * 768

    with patch("apps.intelligence.embeddings.OpenAI") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        # Provedor devolve fora de ordem: index 1 = vec_a, index 0 = vec_b
        from types import SimpleNamespace

        mock_client.embeddings.create.return_value = SimpleNamespace(
            data=[
                SimpleNamespace(embedding=vec_b, index=1),
                SimpleNamespace(embedding=vec_a, index=0),
            ],
            model="openai/text-embedding-3-small",
        )

        adapter = OpenRouterEmbeddingAdapter()
        vectors = adapter.embed_documents_batch([("T1", "C1"), ("T2", "C2")])

        # Ordenado por index: primeiro input recebe vec_a
        assert vectors[0] == vec_a
        assert vectors[1] == vec_b


def test_openrouter_adapter_requires_api_key(monkeypatch):
    from apps.intelligence.embeddings import OpenRouterEmbeddingAdapter

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        OpenRouterEmbeddingAdapter()


def test_get_embedding_adapter_prefers_openrouter(monkeypatch):
    from apps.intelligence.embeddings import (
        MockEmbeddingAdapter,
        OpenRouterEmbeddingAdapter,
        get_embedding_adapter,
    )

    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openrouter")
    with patch("apps.intelligence.embeddings.OpenAI"):
        adapter = get_embedding_adapter()
        assert isinstance(adapter, OpenRouterEmbeddingAdapter)

    # Provider explícito sobrepõe chaves presentes
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    adapter = get_embedding_adapter()
    assert isinstance(adapter, MockEmbeddingAdapter)


def test_local_embedding_adapter_uses_e5_prefixes_batch_and_l2_normalization(monkeypatch):
    from apps.intelligence.embeddings import LocalEmbeddingAdapter

    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    value = 1 / math.sqrt(768)
    model = MagicMock()
    model.encode.return_value = [[value] * 768, [value] * 768]

    with patch(
        "apps.intelligence.embeddings._load_local_sentence_transformer",
        return_value=model,
    ) as loader:
        adapter = LocalEmbeddingAdapter(batch_size=2)
        vectors = adapter.embed_documents_batch(
            [("Edital", "Texto A"), ("Edital", "Texto B")]
        )
        query = adapter.embed_query("qual o prazo?")

    assert len(vectors) == 2
    assert len(query) == 768
    assert adapter.provider == "local"
    assert adapter.model_name == "intfloat/multilingual-e5-base"
    assert adapter.normalization == "L2"
    assert len(adapter.preprocessing_fingerprint) > 20
    assert loader.call_count == 1
    document_call = model.encode.call_args_list[0].args[0]
    query_call = model.encode.call_args_list[1].args[0]
    assert document_call == ["passage: Edital\nTexto A", "passage: Edital\nTexto B"]
    assert query_call == ["query: qual o prazo?"]
    assert model.encode.call_args.kwargs["normalize_embeddings"] is True
    assert model.encode.call_args.kwargs["batch_size"] == 2


def test_local_embedding_adapter_rejects_wrong_dimension(monkeypatch):
    from apps.intelligence.embeddings import LocalEmbeddingAdapter

    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    model = MagicMock()
    model.encode.return_value = [[0.1] * 512]

    with patch(
        "apps.intelligence.embeddings._load_local_sentence_transformer",
        return_value=model,
    ):
        with pytest.raises(ValueError, match="768"):
            LocalEmbeddingAdapter().embed_query("pergunta")
