import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def force_mock_ai_providers():
    """
    Garante determinismo e ausência de chamadas externas na suíte de testes.

    Providers de IA (embeddings e RAG) devem ser mockados nos testes conforme o
    contrato de CI; chaves reais presentes no ambiente nunca devem acionar
    chamadas de rede durante pytest.
    """
    os.environ["GEMINI_API_KEY"] = "mock"
    os.environ["OPENROUTER_API_KEY"] = "mock"
    os.environ["LLM_PROVIDER"] = "mock"
    os.environ["EMBEDDING_PROVIDER"] = "mock"
    yield


@pytest.fixture(autouse=True)
def clear_cache_between_tests():
    """Evita que limites Redis de um teste contaminem o teste seguinte."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
