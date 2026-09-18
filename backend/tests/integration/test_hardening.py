import pytest
from django.core.cache import cache
from rest_framework.exceptions import Throttled
from rest_framework.test import APIClient

from apps.core.throttling import LoginThrottle, RegisterThrottle
from apps.tenders.storage import LocalStorageAdapter

pytestmark = pytest.mark.django_db


def test_cookie_mutation_requires_csrf_token():
    client = APIClient(enforce_csrf_checks=True)
    response = client.post(
        "/api/auth/register/",
        {
            "companyName": "Empresa CSRF",
            "email": "csrf@example.com",
            "password": "Password123!",
        },
        format="json",
    )

    assert response.status_code == 403


def test_cookie_mutation_accepts_token_from_csrf_endpoint():
    client = APIClient(enforce_csrf_checks=True)
    csrf_response = client.get("/api/auth/csrf/")
    csrf_token = csrf_response.json()["csrfToken"]

    response = client.post(
        "/api/auth/register/",
        {
            "companyName": "Empresa CSRF válida",
            "email": "csrf-valid@example.com",
            "password": "Password123!",
        },
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert response.status_code == 201


def test_login_throttle_ignores_untrusted_forwarded_for():
    request = APIClient().post(
        "/api/auth/token/",
        {},
        format="json",
        REMOTE_ADDR="127.0.0.1",
        HTTP_X_FORWARDED_FOR="attacker-controlled",
    ).wsgi_request

    assert LoginThrottle().get_ident(request) == "127.0.0.1"


def test_throttle_failure_is_fail_closed(monkeypatch):
    throttle = RegisterThrottle()
    request = APIClient().post("/api/auth/register/", {}, format="json").wsgi_request

    monkeypatch.setattr(throttle, "cache", cache)
    def redis_failure(*args, **kwargs):
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr(cache, "get", redis_failure)

    with pytest.raises(Throttled):
        throttle.allow_request(request, None)


def test_register_throttle_scope_is_available(settings):
    assert settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["register"]
    assert settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["refresh"]
    assert settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["upload"]


def test_storage_rejects_path_traversal(tmp_path):
    adapter = LocalStorageAdapter(str(tmp_path))

    with pytest.raises(ValueError):
        adapter.exists("../../etc/passwd")


def test_document_chunks_expose_current_embedding_provider(settings):
    from apps.pipeline.models import DocumentChunk

    field = DocumentChunk._meta.get_field("embedding_provider")
    assert field.default == "mock"
    assert settings.EMBEDDING_DIMENSIONS == 768
