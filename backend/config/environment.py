import os
from urllib.parse import unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ImproperlyConfigured(f"Configure {name} no ambiente.")
    return value


def embedding_dimensions():
    if os.environ.get("LOCAL_EMBEDDING_DIMENSIONS", "768") != "768":
        raise ImproperlyConfigured("LOCAL_EMBEDDING_DIMENSIONS deve ser 768.")
    return 768


def configured_llm_provider():
    provider = os.environ.get("LLM_PROVIDER", "opencode").strip().lower()
    if provider not in {"opencode", "openrouter", "gemini", "mock"}:
        raise ValueError("LLM_PROVIDER deve ser opencode, openrouter, gemini ou mock.")
    return provider


def configured_embedding_provider():
    provider = os.environ.get("EMBEDDING_PROVIDER", "local").strip().lower()
    if provider not in {"local", "openrouter", "gemini", "mock"}:
        raise ValueError(
            "EMBEDDING_PROVIDER deve ser local, openrouter, gemini ou mock."
        )
    return provider


def database_config():
    try:
        url = urlsplit(required("DATABASE_URL"))
        if url.scheme not in {"postgres", "postgresql"} or not url.hostname or not url.path[1:]:
            raise ValueError
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(url.path[1:]),
            "USER": unquote(url.username or ""),
            "PASSWORD": unquote(url.password or ""),
            "HOST": url.hostname,
            "PORT": url.port or 5432,
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {"connect_timeout": 5},
        }
    except ValueError:
        raise ImproperlyConfigured("DATABASE_URL deve ser PostgreSQL válida.") from None
