import hashlib
import math
import os
from functools import lru_cache
from typing import Any

from django.conf import settings
from google import genai
from google.genai import types
from openai import OpenAI

DEFAULT_EMBEDDING_MODEL = "gemini-embedding-2"
DEFAULT_EMBEDDING_DIMENSIONS = 768
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_EMBEDDING_MODEL = "openai/text-embedding-3-small"
DEFAULT_LOCAL_EMBEDDING_MODEL = "intfloat/multilingual-e5-base"
EMBEDDING_MODEL_VERSION = "v1"
EMBEDDING_NORMALIZATION = "NFKC"
EMBEDDING_PREPROCESSING_FINGERPRINT = "v2-pdf-layout-ocr-sentence"


class GeminiEmbeddingAdapter:
    """
    Adapter para geração de embeddings via SDK oficial google-genai com Gemini Embedding 2.
    - Dimensão configurada para 768 (validada na resposta).
    - Formatos: instruções textuais de documento e consulta compatíveis com Embedding 2.
    - Chave de API lida estritamente do ambiente GEMINI_API_KEY ou parâmetro explícito.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        expected_dimensions: int | None = None,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable is required for GeminiEmbeddingAdapter."
            )

        self.model_name = (
            model_name
            or getattr(settings, "GEMINI_EMBEDDING_MODEL", None)
            or DEFAULT_EMBEDDING_MODEL
        )
        self.expected_dimensions = (
            expected_dimensions
            or getattr(settings, "EMBEDDING_DIMENSIONS", None)
            or DEFAULT_EMBEDDING_DIMENSIONS
        )

        self.client = genai.Client(api_key=self.api_key)
        self.provider = "gemini"
        self.model_version = EMBEDDING_MODEL_VERSION
        self.normalization = EMBEDDING_NORMALIZATION
        self.preprocessing_fingerprint = EMBEDDING_PREPROCESSING_FINGERPRINT

    def _validate_vector(self, vector: list[float]) -> list[float]:
        if len(vector) != self.expected_dimensions:
            raise ValueError(
                f"A dimensão retornada ({len(vector)}) é diferente da dimensão esperada "
                f"({self.expected_dimensions})."
            )
        return vector

    def embed_document(self, title: str, text: str) -> list[float]:
        """Gera embedding de documento no formato recomendado pelo Embedding 2."""
        config = types.EmbedContentConfig(
            output_dimensionality=self.expected_dimensions,
        )
        response = self.client.models.embed_content(
            model=self.model_name,
            contents=f"title: {title} | text: {text}",
            config=config,
        )
        vector = response.embeddings[0].values
        return self._validate_vector(vector)

    def embed_documents_batch(self, documents: list[tuple[str, str]]) -> list[list[float]]:
        """Gera embeddings para um lote de pares (title, text)."""
        vectors: list[list[float]] = []
        for title, text in documents:
            vectors.append(self.embed_document(title=title, text=text))
        return vectors

    def embed_query(self, query: str) -> list[float]:
        """Gera embedding de consulta no formato recomendado pelo Embedding 2."""
        config = types.EmbedContentConfig(
            output_dimensionality=self.expected_dimensions,
        )
        response = self.client.models.embed_content(
            model=self.model_name,
            contents=f"task: search result | query: {query}",
            config=config,
        )
        vector = response.embeddings[0].values
        return self._validate_vector(vector)


class OpenRouterEmbeddingAdapter:
    """
    Adapter de embeddings OpenAI-compatible via OpenRouter (POST /embeddings).
    - Modelo padrão: openai/text-embedding-3-small com dimensions=768
      (matryoshka), mantendo o schema pgvector(768) sem migração.
    - input_type distingue documento (search_document) de consulta (search_query).
    - Chave lida de OPENROUTER_API_KEY; base URL configurável.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        expected_dimensions: int | None = None,
        base_url: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY environment variable is required for "
                "OpenRouterEmbeddingAdapter."
            )
        self.model_name = (
            model_name
            or getattr(settings, "OPENROUTER_EMBEDDING_MODEL", None)
            or DEFAULT_OPENROUTER_EMBEDDING_MODEL
        )
        self.expected_dimensions = (
            expected_dimensions
            or getattr(settings, "EMBEDDING_DIMENSIONS", None)
            or DEFAULT_EMBEDDING_DIMENSIONS
        )
        self.base_url = (
            base_url
            or getattr(settings, "OPENROUTER_BASE_URL", None)
            or DEFAULT_OPENROUTER_BASE_URL
        )

        self.client = OpenAI(
            api_key=self.api_key, base_url=self.base_url, timeout=30.0, max_retries=1
        )
        self.provider = "openrouter"
        self.model_version = EMBEDDING_MODEL_VERSION
        self.normalization = EMBEDDING_NORMALIZATION
        self.preprocessing_fingerprint = EMBEDDING_PREPROCESSING_FINGERPRINT

    def _validate_vector(self, vector: list[float]) -> list[float]:
        if len(vector) != self.expected_dimensions:
            raise ValueError(
                f"A dimensão retornada ({len(vector)}) é diferente da dimensão esperada "
                f"({self.expected_dimensions})."
            )
        return vector

    def _embed_batch(self, inputs: list[str], input_type: str) -> list[list[float]]:
        response = self.client.embeddings.create(
            model=self.model_name,
            input=inputs,
            dimensions=self.expected_dimensions,
            extra_body={"input_type": input_type},
        )
        ordered = sorted(response.data, key=lambda item: item.index)
        return [self._validate_vector(list(item.embedding)) for item in ordered]

    def embed_document(self, title: str, text: str) -> list[float]:
        return self._embed_batch([f"title: {title} | text: {text}"], "search_document")[0]

    def embed_documents_batch(self, documents: list[tuple[str, str]]) -> list[list[float]]:
        inputs = [f"title: {title} | text: {text}" for title, text in documents]
        return self._embed_batch(inputs, "search_document")

    def embed_query(self, query: str) -> list[float]:
        return self._embed_batch(
            [f"task: search result | query: {query}"], "search_query"
        )[0]


@lru_cache(maxsize=4)
def _load_local_sentence_transformer(
    model_name: str, revision: str, device: str, cache_dir: str
):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        model_name,
        revision=revision,
        device=device,
        cache_folder=cache_dir or None,
    )


class LocalEmbeddingAdapter:
    """Adapter CPU-first para o modelo local multilingual-e5-base."""

    def __init__(
        self,
        model_name: str | None = None,
        expected_dimensions: int | None = None,
        device: str | None = None,
        batch_size: int | None = None,
        revision: str | None = None,
        cache_dir: str | None = None,
    ):
        self.model_name = (
            model_name
            or getattr(settings, "LOCAL_EMBEDDING_MODEL", None)
            or DEFAULT_LOCAL_EMBEDDING_MODEL
        )
        self.expected_dimensions = (
            expected_dimensions
            or getattr(settings, "EMBEDDING_DIMENSIONS", None)
            or DEFAULT_EMBEDDING_DIMENSIONS
        )
        self.device = device or getattr(settings, "LOCAL_EMBEDDING_DEVICE", "cpu")
        self.batch_size = batch_size or getattr(settings, "LOCAL_EMBEDDING_BATCH_SIZE", 32)
        self.revision = revision or getattr(settings, "LOCAL_EMBEDDING_REVISION", "main")
        self.cache_dir = cache_dir or getattr(settings, "LOCAL_EMBEDDING_CACHE_DIR", "")
        if self.expected_dimensions != DEFAULT_EMBEDDING_DIMENSIONS:
            raise ValueError("LOCAL_EMBEDDING_DIMENSIONS deve ser 768.")
        if self.batch_size < 1:
            raise ValueError("LOCAL_EMBEDDING_BATCH_SIZE deve ser positivo.")

        self.provider = "local"
        self.model_version = self.revision
        self.normalization = "L2"
        fingerprint_input = (
            f"model={self.model_name}|revision={self.revision}|device={self.device}|"
            "document_prefix=passage:|query_prefix=query:|normalize_embeddings=true"
        )
        self.preprocessing_fingerprint = (
            f"local-e5-v1-{hashlib.sha256(fingerprint_input.encode()).hexdigest()[:32]}"
        )
        self._loaded_model = None

    @property
    def model(self):
        if self._loaded_model is None:
            self._loaded_model = _load_local_sentence_transformer(
                self.model_name, self.revision, self.device, self.cache_dir
            )
        return self._loaded_model

    def _validate_vector(self, vector: Any) -> list[float]:
        values = vector.tolist() if hasattr(vector, "tolist") else list(vector)
        if len(values) != self.expected_dimensions:
            raise ValueError(
                f"A dimensão retornada ({len(values)}) é diferente da dimensão esperada "
                f"({self.expected_dimensions})."
            )
        norm = math.sqrt(sum(float(value) ** 2 for value in values))
        if not math.isclose(norm, 1.0, rel_tol=1e-3, abs_tol=1e-3):
            raise ValueError("O vetor local não está normalizado por norma L2.")
        return [float(value) for value in values]

    def _encode(self, inputs: list[str]) -> list[list[float]]:
        vectors = self.model.encode(
            inputs,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [self._validate_vector(vector) for vector in vectors]

    def embed_document(self, title: str, text: str) -> list[float]:
        return self._encode([f"passage: {title}\n{text}"])[0]

    def embed_documents_batch(self, documents: list[tuple[str, str]]) -> list[list[float]]:
        return self._encode([f"passage: {title}\n{text}" for title, text in documents])

    def embed_query(self, query: str) -> list[float]:
        return self._encode([f"query: {query}"])[0]


class MockEmbeddingAdapter:
    """
    Adapter mock determinístico para testes e execução local sem credenciais externas.
    Gera vetores normalizados de 768 dimensões baseados no conteúdo textual.
    A busca combina esses vetores com reranking lexical para manter resultados
    úteis offline, sem sugerir que o mock tenha compreensão semântica.
    """

    def __init__(
        self,
        expected_dimensions: int | None = None,
    ):
        self.expected_dimensions = (
            expected_dimensions
            or getattr(settings, "EMBEDDING_DIMENSIONS", None)
            or DEFAULT_EMBEDDING_DIMENSIONS
        )
        self.provider = "mock"
        self.model_name = "mock-embedding-v1"
        self.model_version = EMBEDDING_MODEL_VERSION
        self.normalization = EMBEDDING_NORMALIZATION
        self.preprocessing_fingerprint = EMBEDDING_PREPROCESSING_FINGERPRINT

    def _generate_vector(self, text: str) -> list[float]:
        import hashlib
        import math

        h = hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(h[:8], "big")
        values: list[float] = []
        for _ in range(self.expected_dimensions):
            seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
            val = (seed / 0x7FFFFFFF) * 2.0 - 1.0
            values.append(val)
        norm = math.sqrt(sum(x * x for x in values)) or 1.0
        return [round(x / norm, 6) for x in values]

    def embed_document(self, title: str, text: str) -> list[float]:
        return self._generate_vector(f"{title}\n{text}")

    def embed_documents_batch(self, documents: list[tuple[str, str]]) -> list[list[float]]:
        return [self.embed_document(title=title, text=text) for title, text in documents]

    def embed_query(self, query: str) -> list[float]:
        return self._generate_vector(query)


def get_embedding_metadata(adapter) -> dict[str, str | int]:
    """Retorna a identidade persistível do espaço vetorial atual."""
    return {
        "provider": adapter.provider,
        "model_name": adapter.model_name,
        "model_version": adapter.model_version,
        "dimensions": adapter.expected_dimensions,
        "normalization": adapter.normalization,
        "preprocessing_fingerprint": adapter.preprocessing_fingerprint,
    }


def get_embedding_adapter(
    api_key: str | None = None,
) -> (
    LocalEmbeddingAdapter
    | OpenRouterEmbeddingAdapter
    | GeminiEmbeddingAdapter
    | MockEmbeddingAdapter
):
    """
    Retorna o adapter adequado conforme EMBEDDING_PROVIDER.
    O provider é explícito; não há fallback baseado em chaves presentes no ambiente.
    """
    provider = os.environ.get("EMBEDDING_PROVIDER", "local").strip().lower()
    gemini_key = api_key or os.environ.get("GEMINI_API_KEY")
    or_key = os.environ.get("OPENROUTER_API_KEY")
    if provider == "local":
        return LocalEmbeddingAdapter()
    if provider == "mock":
        return MockEmbeddingAdapter()
    if provider == "openrouter":
        return OpenRouterEmbeddingAdapter(api_key=or_key)
    if provider == "gemini":
        return GeminiEmbeddingAdapter(api_key=gemini_key)
    raise ValueError(
        "EMBEDDING_PROVIDER deve ser local, openrouter, gemini ou mock."
    )
