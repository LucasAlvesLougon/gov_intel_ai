import uuid
from unittest.mock import patch

import pytest
from rest_framework.exceptions import PermissionDenied

from apps.core.models import Company, User
from apps.core.permissions import IsTenantMember, filter_by_tenant, get_user_company

pytestmark = pytest.mark.django_db


def test_register_creates_company_and_owner_and_returns_access_with_refresh_cookie(client):
    payload = {
        "companyName": "Alfa Saúde",
        "email": "demo@example.com",
        "password": "SenhaForte123!",
    }
    response = client.post("/api/auth/register/", payload, content_type="application/json")
    assert response.status_code == 201

    data = response.json()
    assert "accessToken" in data
    assert "refreshToken" not in data

    user_data = data["user"]
    assert user_data["email"] == "demo@example.com"
    assert user_data["role"] == "OWNER"
    assert uuid.UUID(user_data["id"])

    company_data = data["company"]
    assert company_data["name"] == "Alfa Saúde"
    assert company_data["slug"].startswith("alfa-saude-")
    assert uuid.UUID(company_data["id"])

    user = User.objects.get(email="demo@example.com")
    assert user.company.name == "Alfa Saúde"
    assert user.role == "OWNER"
    assert user.check_password("SenhaForte123!")

    # Cookie do refresh token
    assert "refresh_token" in response.cookies
    refresh_cookie = response.cookies["refresh_token"]
    assert refresh_cookie["httponly"] is True
    assert refresh_cookie["samesite"].lower() == "lax"


def test_register_duplicate_email_returns_409_in_envelope(client):
    payload1 = {
        "companyName": "Empresa 1",
        "email": "owner@example.com",
        "password": "SenhaForte123!",
    }
    r1 = client.post("/api/auth/register/", payload1, content_type="application/json")
    assert r1.status_code == 201

    payload2 = {
        "companyName": "Empresa 2",
        "email": "OWNER@example.com",
        "password": "OutraSenhaForte456!",
    }
    r2 = client.post("/api/auth/register/", payload2, content_type="application/json")
    assert r2.status_code == 409
    body = r2.json()
    assert "error" in body
    assert body["error"]["code"] == "CONFLICT"
    assert isinstance(body["error"]["message"], str)
    assert isinstance(body["error"]["details"], dict)

    # A segunda empresa não pode ter sido persistida
    assert Company.objects.count() == 1
    assert User.objects.count() == 1


def test_register_atomic_rollback_on_user_failure(client):
    payload = {
        "companyName": "Empresa Falha",
        "email": "fail@example.com",
        "password": "SenhaForte123!",
    }
    with patch.object(
        User.objects,
        "create_user",
        side_effect=RuntimeError("Simulated user creation failure"),
    ):
        with pytest.raises(RuntimeError):
            client.post("/api/auth/register/", payload, content_type="application/json")

    assert Company.objects.filter(name="Empresa Falha").count() == 0
    assert User.objects.filter(email="fail@example.com").count() == 0


def test_register_invalid_payload_returns_400_in_envelope(client):
    payload = {
        "companyName": "",
        "email": "invalid-email",
        "password": "123",
    }
    response = client.post("/api/auth/register/", payload, content_type="application/json")
    assert response.status_code == 400
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "details" in body["error"]


def test_login_valid_credentials_returns_access_and_cookie_refresh(client):
    register_payload = {
        "companyName": "Empresa Login",
        "email": "login@example.com",
        "password": "SenhaForte123!",
    }
    client.post("/api/auth/register/", register_payload, content_type="application/json")

    login_payload = {
        "email": "LOGIN@Example.com ",
        "password": "SenhaForte123!",
    }
    response = client.post("/api/auth/token/", login_payload, content_type="application/json")
    assert response.status_code == 200
    data = response.json()
    assert "accessToken" in data
    assert "refreshToken" not in data
    assert data["user"]["email"] == "login@example.com"
    assert data["company"]["name"] == "Empresa Login"

    assert "refresh_token" in response.cookies
    assert response.cookies["refresh_token"]["httponly"] is True


def test_login_invalid_credentials_does_not_reveal_email_existence(client):
    register_payload = {
        "companyName": "Empresa Segura",
        "email": "real@example.com",
        "password": "SenhaForte123!",
    }
    client.post("/api/auth/register/", register_payload, content_type="application/json")

    # Senha incorreta para email existente
    r1 = client.post(
        "/api/auth/token/",
        {"email": "real@example.com", "password": "WrongPassword!"},
        content_type="application/json",
    )
    # Email inexistente
    r2 = client.post(
        "/api/auth/token/",
        {"email": "ghost@example.com", "password": "WrongPassword!"},
        content_type="application/json",
    )

    assert r1.status_code == 401
    assert r2.status_code == 401
    assert r1.json() == r2.json()
    assert r1.json()["error"]["code"] == "AUTHENTICATION_FAILED"


def test_login_inactive_user_returns_401(client):
    company = Company.objects.create(name="Empresa Inativa")
    user = User.objects.create_user(
        email="inactive@example.com",
        password="SenhaForte123!",
        company=company,
    )
    user.is_active = False
    user.save()

    response = client.post(
        "/api/auth/token/",
        {"email": "inactive@example.com", "password": "SenhaForte123!"},
        content_type="application/json",
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_FAILED"


def test_refresh_rotates_and_blacklists_old_token(client):
    register_payload = {
        "companyName": "Empresa Refresh",
        "email": "refresh@example.com",
        "password": "SenhaForte123!",
    }
    reg_res = client.post("/api/auth/register/", register_payload, content_type="application/json")
    first_cookie = reg_res.cookies["refresh_token"].value

    # Primeiro refresh válido usando cookie
    client.cookies["refresh_token"] = first_cookie
    ref_res = client.post("/api/auth/token/refresh/", content_type="application/json")
    assert ref_res.status_code == 200
    assert "accessToken" in ref_res.json()
    second_cookie = ref_res.cookies["refresh_token"].value
    assert second_cookie != first_cookie

    # Reutilização do primeiro cookie deve falhar (blacklist / reuse detection)
    client.cookies["refresh_token"] = first_cookie
    reuse_res = client.post("/api/auth/token/refresh/", content_type="application/json")
    assert reuse_res.status_code == 401
    assert reuse_res.json()["error"]["code"] == "AUTHENTICATION_FAILED"

    # Reuse detectado revoga também o sucessor da mesma família.
    client.cookies["refresh_token"] = second_cookie
    family_res = client.post("/api/auth/token/refresh/", content_type="application/json")
    assert family_res.status_code == 401


def test_refresh_missing_cookie_returns_401(client):
    client.cookies.clear()
    response = client.post("/api/auth/token/refresh/", content_type="application/json")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_FAILED"


def test_logout_revokes_token_and_clears_cookie(client):
    register_payload = {
        "companyName": "Empresa Logout",
        "email": "logout@example.com",
        "password": "SenhaForte123!",
    }
    reg_res = client.post("/api/auth/register/", register_payload, content_type="application/json")
    refresh_token = reg_res.cookies["refresh_token"].value

    client.cookies["refresh_token"] = refresh_token
    logout_res = client.post("/api/auth/logout/", content_type="application/json")
    assert logout_res.status_code == 204
    assert logout_res.cookies["refresh_token"].value == ""

    # Tentativa de refresh posterior com token revogado retorna 401
    client.cookies["refresh_token"] = refresh_token
    refresh_res = client.post("/api/auth/token/refresh/", content_type="application/json")
    assert refresh_res.status_code == 401


def test_me_returns_authenticated_identity(client):
    register_payload = {
        "companyName": "Empresa Me",
        "email": "me@example.com",
        "password": "SenhaForte123!",
    }
    reg_res = client.post("/api/auth/register/", register_payload, content_type="application/json")
    access_token = reg_res.json()["accessToken"]

    response = client.get(
        "/api/auth/me/",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == "me@example.com"
    assert data["company"]["name"] == "Empresa Me"


def test_me_rejects_unauthenticated_request(client):
    response = client.get("/api/auth/me/")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_FAILED"


def test_csrf_returns_token(client):
    response = client.get("/api/auth/csrf/")
    assert response.status_code == 200
    assert "csrfToken" in response.json()


def test_cors_allows_configured_loopback_frontend_origin(client):
    response = client.options(
        "/api/auth/register/",
        HTTP_ORIGIN="http://127.0.0.1:3000",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type,x-csrftoken",
    )

    assert response.status_code == 200
    assert response["Access-Control-Allow-Origin"] == "http://127.0.0.1:3000"
    assert response["Access-Control-Allow-Credentials"] == "true"

    blocked = client.options(
        "/api/auth/register/",
        HTTP_ORIGIN="https://malicious.example",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type",
    )
    assert "Access-Control-Allow-Origin" not in blocked


def test_tenant_isolation_two_companies_cannot_access_or_impersonate(client):
    # Cria Empresa A e Usuário A
    reg_a = client.post(
        "/api/auth/register/",
        {"companyName": "Empresa A", "email": "user.a@example.com", "password": "Password123!"},
        content_type="application/json",
    )
    token_a = reg_a.json()["accessToken"]
    company_a_id = reg_a.json()["company"]["id"]

    # Cria Empresa B e Usuário B
    reg_b = client.post(
        "/api/auth/register/",
        {"companyName": "Empresa B", "email": "user.b@example.com", "password": "Password123!"},
        content_type="application/json",
    )
    token_b = reg_b.json()["accessToken"]
    company_b_id = reg_b.json()["company"]["id"]

    # Usuário A consulta /me/ -> somente dados da Empresa A
    me_a = client.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {token_a}")
    assert me_a.status_code == 200
    assert me_a.json()["company"]["id"] == company_a_id
    assert me_a.json()["company"]["name"] == "Empresa A"

    # Usuário B consulta /me/ -> somente dados da Empresa B
    me_b = client.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {token_b}")
    assert me_b.status_code == 200
    assert me_b.json()["company"]["id"] == company_b_id
    assert me_b.json()["company"]["name"] == "Empresa B"

    # Usuário A tenta injetar companyId da Empresa B no payload ou query -> ignorado pelo backend
    me_a_tampered = client.get(
        f"/api/auth/me/?companyId={company_b_id}",
        HTTP_AUTHORIZATION=f"Bearer {token_a}",
    )
    assert me_a_tampered.status_code == 200
    assert me_a_tampered.json()["company"]["id"] == company_a_id

    # Verificação de isolamento no nível de ORM/helper
    user_a = User.objects.get(email="user.a@example.com")
    user_b = User.objects.get(email="user.b@example.com")

    # get_user_company deriva estritamente do usuário
    assert get_user_company(user_a).id == uuid.UUID(company_a_id)
    assert get_user_company(user_b).id == uuid.UUID(company_b_id)

    # filter_by_tenant restringe o queryset estritamente ao tenant
    user_qs_for_a = filter_by_tenant(User.objects.all(), user_a)
    assert user_a in user_qs_for_a
    assert user_b not in user_qs_for_a

    # IsTenantMember nega acesso a objetos de outros tenants
    class MockResource:
        def __init__(self, company_id):
            self.company_id = company_id

    resource_b = MockResource(user_b.company_id)
    permission = IsTenantMember()

    class MockRequest:
        def __init__(self, user):
            self.user = user

    request_a = MockRequest(user_a)
    assert permission.has_object_permission(request_a, None, resource_b) is False

    request_b = MockRequest(user_b)
    assert permission.has_object_permission(request_b, None, resource_b) is True


def test_tenant_helpers_reject_unauthenticated():
    class AnonymousUser:
        is_authenticated = False

    with pytest.raises(PermissionDenied):
        get_user_company(AnonymousUser())
