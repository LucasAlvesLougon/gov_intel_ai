import json
import os
from typing import Any
from urllib.parse import urlsplit

from django.conf import settings
from openai import APITimeoutError, AuthenticationError, OpenAI


class LLMProviderError(RuntimeError):
    """Erro seguro na fronteira com um provedor de LLM."""


class LLMConfigurationError(LLMProviderError):
    pass


class LLMAuthenticationError(LLMProviderError):
    pass


class LLMTimeoutError(LLMProviderError):
    pass


class LLMResponseError(LLMProviderError):
    pass


DEFAULT_OPENCODE_BASE_URL = "https://opencode.ai/zen/v1"
DEFAULT_OPENCODE_CHAT_MODEL = "deepseek-v4-flash"


def _required_api_key(api_key: str | None) -> str:
    value = api_key or os.environ.get("OPENCODE_API_KEY", "")
    if not value.strip():
        raise LLMConfigurationError("OPENCODE_API_KEY não configurada.")
    return value


def _validate_base_url(base_url: str) -> str:
    parsed = urlsplit(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise LLMConfigurationError("OPENCODE_BASE_URL deve ser uma URL HTTPS válida.")
    return base_url.rstrip("/")


class OpenCodeChatAdapter:
    """Adapter OpenAI-compatible para o endpoint Chat Completions do OpenCode Zen."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
        *,
        client: Any | None = None,
        validate_model: bool = True,
    ):
        self.api_key = _required_api_key(api_key)
        self.base_url = _validate_base_url(
            base_url
            or getattr(settings, "OPENCODE_BASE_URL", None)
            or DEFAULT_OPENCODE_BASE_URL
        )
        self.model_name = (
            model_name
            or getattr(settings, "OPENCODE_CHAT_MODEL", None)
            or DEFAULT_OPENCODE_CHAT_MODEL
        ).strip()
        if not self.model_name:
            raise LLMConfigurationError("OPENCODE_CHAT_MODEL não configurado.")

        self.client = client or OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=30.0,
            max_retries=1,
        )
        if validate_model:
            self._validate_model_availability()

    def _validate_model_availability(self) -> None:
        try:
            response = self.client.models.list()
            models = getattr(response, "data", response)
            available = {str(item.id) for item in models if getattr(item, "id", None)}
        except AuthenticationError as exc:
            raise LLMAuthenticationError("Autenticação do OpenCode rejeitada.") from exc
        except APITimeoutError as exc:
            raise LLMTimeoutError("Validação do modelo OpenCode expirou.") from exc
        except Exception as exc:
            raise LLMConfigurationError(
                "Não foi possível validar o modelo configurado no OpenCode."
            ) from exc

        if self.model_name not in available:
            raise LLMConfigurationError(
                "O modelo OpenCode configurado não está disponível no endpoint."
            )

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )
        except AuthenticationError as exc:
            raise LLMAuthenticationError("Autenticação do OpenCode rejeitada.") from exc
        except APITimeoutError as exc:
            raise LLMTimeoutError("A chamada ao OpenCode expirou.") from exc
        except Exception as exc:
            raise LLMProviderError("O OpenCode não respondeu de forma utilizável.") from exc

        try:
            content = response.choices[0].message.content
            if not isinstance(content, str):
                raise TypeError
            parsed = json.loads(content)
        except (AttributeError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LLMResponseError("A resposta do OpenCode não é JSON válido.") from exc

        if not isinstance(parsed, dict):
            raise LLMResponseError("A resposta JSON do OpenCode deve ser um objeto.")
        return parsed
