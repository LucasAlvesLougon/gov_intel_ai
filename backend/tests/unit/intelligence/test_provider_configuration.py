from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from openai import APITimeoutError, AuthenticationError

from apps.intelligence.llm import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMResponseError,
    LLMTimeoutError,
    OpenCodeChatAdapter,
)
from config.environment import configured_embedding_provider, configured_llm_provider


def test_llm_and_embedding_provider_selection_is_independent(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")

    assert configured_llm_provider() == "mock"
    assert configured_embedding_provider() == "local"


def test_defaults_are_opencode_and_local(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)

    assert configured_llm_provider() == "opencode"
    assert configured_embedding_provider() == "local"


@pytest.mark.parametrize(
    ("name", "value"),
    [("LLM_PROVIDER", "unknown"), ("EMBEDDING_PROVIDER", "remote")],
)
def test_invalid_provider_configuration_fails_closed(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    getter = configured_llm_provider if name == "LLM_PROVIDER" else configured_embedding_provider

    with pytest.raises(ValueError, match="PROVIDER"):
        getter()


def test_opencode_defaults_to_deepseek_v4_flash_and_validates_model(monkeypatch):
    monkeypatch.setenv("OPENCODE_API_KEY", "test-key")
    client = MagicMock()
    client.models.list.return_value = [SimpleNamespace(id="deepseek-v4-flash")]

    with patch("apps.intelligence.llm.OpenAI", return_value=client) as client_cls:
        adapter = OpenCodeChatAdapter()

    assert adapter.model_name == "deepseek-v4-flash"
    client_cls.assert_called_once_with(
        api_key="test-key",
        base_url="https://opencode.ai/zen/v1",
        timeout=30.0,
        max_retries=1,
    )
    client.models.list.assert_called_once_with()


def test_opencode_rejects_model_not_listed_by_endpoint(monkeypatch):
    monkeypatch.setenv("OPENCODE_API_KEY", "test-key")
    client = MagicMock()
    client.models.list.return_value = [SimpleNamespace(id="mimo-v2.5-free")]

    with patch("apps.intelligence.llm.OpenAI", return_value=client):
        with pytest.raises(LLMConfigurationError, match="modelo OpenCode configurado"):
            OpenCodeChatAdapter()


def test_opencode_returns_validated_json(monkeypatch):
    monkeypatch.setenv("OPENCODE_API_KEY", "test-key")
    client = MagicMock()
    client.models.list.return_value = [SimpleNamespace(id="deepseek-v4-flash")]
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content='{"answer":"ok","citations":[]}')
            )
        ]
    )

    with patch("apps.intelligence.llm.OpenAI", return_value=client):
        adapter = OpenCodeChatAdapter()
        result = adapter.generate_json("system", "user")

    assert result == {"answer": "ok", "citations": []}
    call = client.chat.completions.create.call_args.kwargs
    assert call["model"] == "deepseek-v4-flash"
    assert call["response_format"] == {"type": "json_object"}
    assert call["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "user"},
    ]


def test_opencode_rejects_malformed_json(monkeypatch):
    monkeypatch.setenv("OPENCODE_API_KEY", "test-key")
    client = MagicMock()
    client.models.list.return_value = [SimpleNamespace(id="deepseek-v4-flash")]
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="not-json"))]
    )

    with patch("apps.intelligence.llm.OpenAI", return_value=client):
        with pytest.raises(LLMResponseError, match="JSON"):
            OpenCodeChatAdapter().generate_json("system", "user")


@pytest.mark.parametrize(
    ("error", "mapped"),
    [
        (AuthenticationError("bad", response=MagicMock(), body={}), LLMAuthenticationError),
        (APITimeoutError(request=MagicMock()), LLMTimeoutError),
    ],
)
def test_opencode_maps_provider_errors_without_secret_details(monkeypatch, error, mapped):
    monkeypatch.setenv("OPENCODE_API_KEY", "test-key")
    client = MagicMock()
    client.models.list.return_value = [SimpleNamespace(id="deepseek-v4-flash")]
    client.chat.completions.create.side_effect = error

    with patch("apps.intelligence.llm.OpenAI", return_value=client):
        with pytest.raises(mapped) as raised:
            OpenCodeChatAdapter().generate_json("system", "user")

    assert "test-key" not in str(raised.value)
