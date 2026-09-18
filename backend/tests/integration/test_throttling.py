import uuid
from unittest.mock import patch

import pytest
import redis
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient

from apps.core.jwt_utils import get_tokens_for_user
from apps.core.models import Company, User
from apps.core.throttling import (
    ChatThrottle,
    LoginThrottle,
    SearchThrottle,
)
from apps.pipeline.models import DocumentChunk
from apps.tenders.models import Tender

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def company_a():
    return Company.objects.create(name="Tenant Throttle A")


@pytest.fixture
def company_b():
    return Company.objects.create(name="Tenant Throttle B")


@pytest.fixture
def user_a(company_a):
    return User.objects.create_user(
        email="throttle_a@test.com",
        password="Password123!",
        company=company_a,
    )


@pytest.fixture
def user_b(company_b):
    return User.objects.create_user(
        email="throttle_b@test.com",
        password="Password123!",
        company=company_b,
    )


@pytest.fixture
def auth_client_a(user_a):
    client = APIClient()
    tokens = get_tokens_for_user(user_a)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


@pytest.fixture
def auth_client_b(user_b):
    client = APIClient()
    tokens = get_tokens_for_user(user_b)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


@pytest.fixture
def processed_tender_a(company_a):
    tender = Tender.objects.create(
        company=company_a,
        title="Edital Throttle Test A",
        status="PROCESSED",
    )
    vec = [0.0] * 768
    vec[0] = 0.9
    vec[1] = 0.1
    DocumentChunk.objects.create(
        company=company_a,
        tender=tender,
        generation=1,
        chunk_index=0,
        page_number=1,
        start_char_offset=0,
        end_char_offset=25,
        text="Texto de teste para busca",
        text_hash="hash_search_1",
        embedding=vec,
        is_current=True,
        staged=False,
    )
    return tender


def test_throttle_key_namespace_matches_contract(user_a):
    """Verifica que as chaves de cache seguem o formato govintel:v1:throttle:{ident}:{endpoint}."""
    client = APIClient()
    req = client.get("/").wsgi_request

    # Login throttle: usa IP
    login_throttle = LoginThrottle()
    login_key = login_throttle.get_cache_key(req, None)
    assert login_key == "govintel:v1:throttle:127.0.0.1:login"

    # Search throttle com usuário autenticado: usa ID do usuário
    req.user = user_a
    search_throttle = SearchThrottle()
    search_key = search_throttle.get_cache_key(req, None)
    assert search_key == f"govintel:v1:throttle:{user_a.id}:search"

    # Chat throttle com usuário autenticado: usa ID do usuário
    chat_throttle = ChatThrottle()
    chat_key = chat_throttle.get_cache_key(req, None)
    assert chat_key == f"govintel:v1:throttle:{user_a.id}:chat"


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "rest_framework_simplejwt.authentication.JWTAuthentication",
        ),
        "DEFAULT_PERMISSION_CLASSES": (
            "rest_framework.permissions.IsAuthenticated",
        ),
        "DEFAULT_THROTTLE_RATES": {
            "login": "2/minute",
            "search": "2/minute",
            "chat": "2/minute",
        },
        "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
    }
)
def test_login_throttling_triggers_429(user_a):
    """POST /api/auth/token/ excede limite e retorna 429 no envelope padrão."""
    client = APIClient()
    payload = {"email": user_a.email, "password": "Password123!"}

    # 1ª e 2ª chamadas: permitidas (status 200)
    res1 = client.post("/api/auth/token/", payload, format="json")
    assert res1.status_code == 200

    res2 = client.post("/api/auth/token/", payload, format="json")
    assert res2.status_code == 200

    # 3ª chamada: bloqueada por throttling (429)
    res3 = client.post("/api/auth/token/", payload, format="json")
    assert res3.status_code == 429
    body = res3.json()
    assert body["error"]["code"] == "RATE_LIMITED"
    assert body["error"]["message"] == "Muitas requisições. Tente novamente mais tarde."
    assert body["error"]["details"] == {}
    assert "Retry-After" in res3.headers


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "rest_framework_simplejwt.authentication.JWTAuthentication",
        ),
        "DEFAULT_PERMISSION_CLASSES": (
            "rest_framework.permissions.IsAuthenticated",
        ),
        "DEFAULT_THROTTLE_RATES": {
            "login": "2/minute",
            "search": "2/minute",
            "chat": "2/minute",
        },
        "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
    }
)
def test_search_throttling_triggers_429(auth_client_a, processed_tender_a):
    """POST /api/search/semantic/ excede limite e retorna 429 no envelope padrão."""
    payload = {"query": "teste"}

    res1 = auth_client_a.post("/api/search/semantic/", payload, format="json")
    assert res1.status_code == 200

    res2 = auth_client_a.post("/api/search/semantic/", payload, format="json")
    assert res2.status_code == 200

    res3 = auth_client_a.post("/api/search/semantic/", payload, format="json")
    assert res3.status_code == 429
    body = res3.json()
    assert body["error"]["code"] == "RATE_LIMITED"
    assert body["error"]["message"] == "Muitas requisições. Tente novamente mais tarde."
    assert body["error"]["details"] == {}
    assert "Retry-After" in res3.headers


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "rest_framework_simplejwt.authentication.JWTAuthentication",
        ),
        "DEFAULT_PERMISSION_CLASSES": (
            "rest_framework.permissions.IsAuthenticated",
        ),
        "DEFAULT_THROTTLE_RATES": {
            "login": "2/minute",
            "search": "2/minute",
            "chat": "2/minute",
        },
        "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
    }
)
def test_chat_throttling_triggers_429(auth_client_a, processed_tender_a):
    """POST /api/tenders/{id}/chat/ excede limite e retorna 429 no envelope padrão."""
    payload = {"message": "Qual é o objeto do edital?"}

    res1 = auth_client_a.post(
        f"/api/tenders/{processed_tender_a.id}/chat/", payload, format="json"
    )
    assert res1.status_code == 200

    res2 = auth_client_a.post(
        f"/api/tenders/{processed_tender_a.id}/chat/", payload, format="json"
    )
    assert res2.status_code == 200

    res3 = auth_client_a.post(
        f"/api/tenders/{processed_tender_a.id}/chat/", payload, format="json"
    )
    assert res3.status_code == 429
    body = res3.json()
    assert body["error"]["code"] == "RATE_LIMITED"
    assert body["error"]["message"] == "Muitas requisições. Tente novamente mais tarde."
    assert body["error"]["details"] == {}
    assert "Retry-After" in res3.headers


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "rest_framework_simplejwt.authentication.JWTAuthentication",
        ),
        "DEFAULT_PERMISSION_CLASSES": (
            "rest_framework.permissions.IsAuthenticated",
        ),
        "DEFAULT_THROTTLE_RATES": {
            "login": "2/minute",
            "search": "2/minute",
            "chat": "2/minute",
        },
        "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
    }
)
def test_throttling_limits_are_independent_per_user_and_endpoint(
    auth_client_a, auth_client_b, user_a, processed_tender_a
):
    """
    Verifica que:
    1. Usuário A esgotar busca não impede Usuário B de buscar.
    2. Usuário A esgotar busca não impede Usuário A de conversar no chat.
    3. Esgotar login de um IP não impede outro IP.
    """
    # 1. Usuário A esgota o throttle de busca
    for _ in range(2):
        res = auth_client_a.post("/api/search/semantic/", {"query": "teste"}, format="json")
        assert res.status_code == 200

    res_a_blocked = auth_client_a.post(
        "/api/search/semantic/", {"query": "teste"}, format="json"
    )
    assert res_a_blocked.status_code == 429

    # 2. Usuário B ainda pode buscar com sucesso (independência por usuário)
    res_b_ok = auth_client_b.post("/api/search/semantic/", {"query": "teste"}, format="json")
    assert res_b_ok.status_code == 200

    # 3. Usuário A ainda pode usar o chat (independência por endpoint)
    res_chat = auth_client_a.post(
        f"/api/tenders/{processed_tender_a.id}/chat/",
        {"message": "Pergunta permitida"},
        format="json",
    )
    assert res_chat.status_code == 200

    # 4. Login com IPs diferentes
    client_ip1 = APIClient(REMOTE_ADDR="192.168.1.100")
    client_ip2 = APIClient(REMOTE_ADDR="192.168.1.200")
    login_payload = {"email": user_a.email, "password": "Password123!"}

    for _ in range(2):
        res = client_ip1.post("/api/auth/token/", login_payload, format="json")
        assert res.status_code == 200

    # IP 1 bloqueado
    assert client_ip1.post("/api/auth/token/", login_payload, format="json").status_code == 429

    # IP 2 liberado
    assert client_ip2.post("/api/auth/token/", login_payload, format="json").status_code == 200


def test_redis_details_do_not_leak_on_internal_server_error(user_a):
    """
    Erros internos que envolvem Redis ou infraestrutura retornam 500
    no envelope comum sem vazar strings de conexão, hosts ou stack traces.
    """
    client = APIClient(raise_request_exception=False)
    tokens = get_tokens_for_user(user_a)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    with patch(
        "apps.intelligence.views.VectorSearchRepository.search",
        side_effect=redis.exceptions.ConnectionError(
            "Connection refused to redis://secret_user:super_secret_password@redis_cluster:6379/0"
        ),
    ):
        res = client.post(
            "/api/search/semantic/", {"query": "falha interna"}, format="json"
        )
        assert res.status_code == 500
        body = res.json()
        assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
        assert body["error"]["message"] == "Erro interno do servidor."
        assert body["error"]["details"] == {}

        # Confirma que detalhes confidenciais não constam na resposta
        raw_text = res.content.decode("utf-8")
        assert "super_secret_password" not in raw_text
        assert "redis_cluster" not in raw_text
        assert "Connection refused" not in raw_text
        assert "Traceback" not in raw_text


def test_global_exception_handler_covers_contract_status_codes(auth_client_a):
    """
    Verifica que o handler global padroniza o envelope para:
    - 401 (não autenticado)
    - 404 (não encontrado)
    - 400 (parser error com JSON malformado)
    """
    # 401 Não autenticado
    unauth_client = APIClient()
    res_401 = unauth_client.get("/api/auth/me/")
    assert res_401.status_code == 401
    assert res_401.json()["error"]["code"] == "AUTHENTICATION_FAILED"
    assert res_401.json()["error"]["details"] == {}

    # 404 Recurso inexistente
    res_404 = auth_client_a.get(f"/api/tenders/{uuid.uuid4()}/")
    assert res_404.status_code == 404
    assert res_404.json()["error"]["code"] == "NOT_FOUND"
    assert res_404.json()["error"]["details"] == {}

    # 400 Parser error (JSON malformado)
    res_parser = auth_client_a.post(
        "/api/search/semantic/",
        data='{"query": "incompleto',
        content_type="application/json",
    )
    assert res_parser.status_code == 400
    body_parser = res_parser.json()
    assert body_parser["error"]["code"] == "VALIDATION_ERROR"
    assert "non_field_errors" in body_parser["error"]["details"]
