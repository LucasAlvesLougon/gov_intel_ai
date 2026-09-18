from unittest.mock import patch

import pytest
from django.db import OperationalError


@pytest.mark.django_db
def test_health_verifies_database_and_returns_no_secrets(client):
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_failure_is_safe_and_not_healthy(client):
    with patch("config.health.connection.cursor", side_effect=OperationalError("private-db-url")):
        response = client.get("/health/")
    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "SERVICE_UNAVAILABLE",
            "message": "Serviço temporariamente indisponível.",
            "details": {},
        }
    }
    assert b"private-db-url" not in response.content


def test_health_rejects_mutation(client):
    assert client.post("/health/").status_code == 405


def test_missing_environment_fails_without_values(monkeypatch):
    from config.environment import required

    monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)
    with pytest.raises(Exception, match="DJANGO_SECRET_KEY"):
        required("DJANGO_SECRET_KEY")


def test_wrong_embedding_dimension_is_rejected(monkeypatch):
    from config.environment import embedding_dimensions

    monkeypatch.setenv("LOCAL_EMBEDDING_DIMENSIONS", "1536")
    with pytest.raises(Exception, match="768"):
        embedding_dimensions()
