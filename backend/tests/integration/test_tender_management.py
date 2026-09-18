import uuid

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.core.models import Company
from apps.tenders.models import Tender
from apps.tenders.storage import get_storage_adapter

pytestmark = pytest.mark.django_db


def create_user_and_token(client, email, company_name):
    reg = client.post(
        "/api/auth/register/",
        {"companyName": company_name, "email": email, "password": "Password123!"},
        content_type="application/json",
    )
    token = reg.json()["accessToken"]
    company_id = reg.json()["company"]["id"]
    return token, company_id


def test_tender_model_creation_and_state_constraints():
    company = Company.objects.create(name="Hospital Central")
    tender = Tender.objects.create(
        company=company,
        title="Edital Medicamentos 2026",
        description="Aquisição de insumos",
        status="PENDING",
        original_filename="edital_01.pdf",
        storage_key="uploads/hospital_central/edital_01.pdf",
        file_size=2048,
    )
    assert isinstance(tender.id, uuid.UUID)
    assert tender.status == "PENDING"
    assert tender.company_id == company.id

    # Verifica os 4 estados documentados
    for valid_status in ["PENDING", "PROCESSING", "PROCESSED", "FAILED"]:
        tender.status = valid_status
        tender.save()
        tender.refresh_from_db()
        assert tender.status == valid_status


def test_list_tenders_scoped_to_authenticated_tenant(client):
    token_a, company_a_id = create_user_and_token(client, "hospital.a@test.com", "Hospital A")
    token_b, company_b_id = create_user_and_token(client, "hospital.b@test.com", "Hospital B")

    company_a = Company.objects.get(id=company_a_id)
    company_b = Company.objects.get(id=company_b_id)

    Tender.objects.create(company=company_a, title="Edital A1", original_filename="a1.pdf")
    Tender.objects.create(company=company_a, title="Edital A2", original_filename="a2.pdf")
    Tender.objects.create(company=company_b, title="Edital B1", original_filename="b1.pdf")

    # Usuário A só vê editais da Empresa A
    res_a = client.get("/api/tenders/", HTTP_AUTHORIZATION=f"Bearer {token_a}")
    assert res_a.status_code == 200
    body_a = res_a.json()
    assert "data" in body_a
    assert "pagination" in body_a
    titles_a = [item["title"] for item in body_a["data"]]
    assert "Edital A1" in titles_a
    assert "Edital A2" in titles_a
    assert "Edital B1" not in titles_a
    assert body_a["pagination"]["totalItems"] == 2

    # Usuário B só vê editais da Empresa B
    res_b = client.get("/api/tenders/", HTTP_AUTHORIZATION=f"Bearer {token_b}")
    assert res_b.status_code == 200
    body_b = res_b.json()
    titles_b = [item["title"] for item in body_b["data"]]
    assert "Edital B1" in titles_b
    assert "Edital A1" not in titles_b
    assert body_b["pagination"]["totalItems"] == 1


def test_list_tenders_pagination_format_and_limits(client):
    token, company_id = create_user_and_token(client, "pag.user@test.com", "Empresa Paginação")
    company = Company.objects.get(id=company_id)

    for i in range(25):
        Tender.objects.create(
            company=company,
            title=f"Edital {i:02d}",
            original_filename=f"edital_{i}.pdf",
        )

    # Página 1 com pageSize 10
    res = client.get(
        "/api/tenders/?page=1&pageSize=10",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["data"]) == 10
    assert body["pagination"]["page"] == 1
    assert body["pagination"]["pageSize"] == 10
    assert body["pagination"]["totalItems"] == 25
    assert body["pagination"]["totalPages"] == 3

    # Página 3 com pageSize 10
    res3 = client.get(
        "/api/tenders/?page=3&pageSize=10",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert len(res3.json()["data"]) == 5


def test_list_tenders_filter_by_status(client):
    token, company_id = create_user_and_token(client, "filter.user@test.com", "Empresa Filtros")
    company = Company.objects.get(id=company_id)

    Tender.objects.create(company=company, title="Edital Pendente", status="PENDING")
    Tender.objects.create(company=company, title="Edital Concluído", status="PROCESSED")

    res = client.get(
        "/api/tenders/?status=PROCESSED",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 1
    assert data[0]["title"] == "Edital Concluído"
    assert data[0]["status"] == "PROCESSED"


def test_get_tender_by_id_scoped_to_tenant(client):
    token_a, comp_a_id = create_user_and_token(client, "detail.a@test.com", "Empresa Detalhe A")
    token_b, comp_b_id = create_user_and_token(client, "detail.b@test.com", "Empresa Detalhe B")

    comp_a = Company.objects.get(id=comp_a_id)
    comp_b = Company.objects.get(id=comp_b_id)

    t_a = Tender.objects.create(company=comp_a, title="Edital A", original_filename="a.pdf")
    t_b = Tender.objects.create(company=comp_b, title="Edital B", original_filename="b.pdf")

    # Usuário A consulta seu próprio edital -> 200
    res_ok = client.get(f"/api/tenders/{t_a.id}/", HTTP_AUTHORIZATION=f"Bearer {token_a}")
    assert res_ok.status_code == 200
    assert res_ok.json()["id"] == str(t_a.id)
    assert res_ok.json()["title"] == "Edital A"

    # Usuário A tenta consultar edital da Empresa B -> 404
    res_not_found = client.get(f"/api/tenders/{t_b.id}/", HTTP_AUTHORIZATION=f"Bearer {token_a}")
    assert res_not_found.status_code == 404
    assert res_not_found.json()["error"]["code"] == "NOT_FOUND"


def test_tenders_requires_authentication(client):
    res = client.get("/api/tenders/")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "AUTHENTICATION_FAILED"


def test_upload_valid_pdf_returns_202_and_saves_to_storage(client):
    token, _ = create_user_and_token(client, "upload.user@test.com", "Empresa Upload")
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Title (Edital Teste) >>\nendobj\n%%EOF"
    uploaded = SimpleUploadedFile("edital.pdf", pdf_bytes, content_type="application/pdf")

    response = client.post(
        "/api/tenders/",
        {"file": uploaded, "title": "Edital Licitação 2026"},
        format="multipart",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "PENDING"
    assert data["title"] == "Edital Licitação 2026"
    assert data["originalFilename"] == "edital.pdf"
    assert data["fileSize"] == len(pdf_bytes)

    # Verifica persistência no banco e storage privado
    tender = Tender.objects.get(id=data["id"])
    assert tender.status == "PENDING"
    assert tender.sha256 != ""
    assert tender.storage_key != ""
    # Nome original nunca é usado como caminho no storage
    assert "edital.pdf" not in tender.storage_key

    adapter = get_storage_adapter()
    assert adapter.exists(tender.storage_key) is True
    saved_bytes = adapter.read_bytes(tender.storage_key)
    assert saved_bytes == pdf_bytes


def test_upload_rejects_empty_file(client):
    token, _ = create_user_and_token(client, "empty.user@test.com", "Empresa Vazia")
    empty_file = SimpleUploadedFile("vazio.pdf", b"", content_type="application/pdf")

    response = client.post(
        "/api/tenders/",
        {"file": empty_file, "title": "Edital Vazio"},
        format="multipart",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_upload_rejects_non_pdf_magic_bytes(client):
    token, _ = create_user_and_token(client, "fake.user@test.com", "Empresa Fake")
    fake_pdf = SimpleUploadedFile(
        "falso.pdf",
        b"PLAIN TEXT CONTENT NOT A PDF",
        content_type="application/pdf",
    )

    response = client.post(
        "/api/tenders/",
        {"file": fake_pdf, "title": "Edital Falso"},
        format="multipart",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_delete_tender_removes_from_database_and_storage(client):
    token, _ = create_user_and_token(client, "delete.user@test.com", "Empresa Delete")
    pdf_bytes = b"%PDF-1.4\nTeste exclusao\n%%EOF"
    uploaded = SimpleUploadedFile("delete.pdf", pdf_bytes, content_type="application/pdf")

    upload_res = client.post(
        "/api/tenders/",
        {"file": uploaded, "title": "Edital Para Deletar"},
        format="multipart",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    tender_id = upload_res.json()["id"]
    tender = Tender.objects.get(id=tender_id)
    storage_key = tender.storage_key

    adapter = get_storage_adapter()
    assert adapter.exists(storage_key) is True

    # Exclusão autorizada pelo tenant
    del_res = client.delete(f"/api/tenders/{tender_id}/", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert del_res.status_code == 204

    # Removido do banco e do storage privado
    assert Tender.objects.filter(id=tender_id).count() == 0
    assert adapter.exists(storage_key) is False


def test_delete_cross_tenant_returns_404(client):
    token_a, _ = create_user_and_token(client, "del.a@test.com", "Empresa Del A")
    token_b, _ = create_user_and_token(client, "del.b@test.com", "Empresa Del B")

    pdf_bytes = b"%PDF-1.4\nTeste isolamento delete\n%%EOF"
    uploaded = SimpleUploadedFile("edital_a.pdf", pdf_bytes, content_type="application/pdf")
    upload_res = client.post(
        "/api/tenders/",
        {"file": uploaded, "title": "Edital A"},
        format="multipart",
        HTTP_AUTHORIZATION=f"Bearer {token_a}",
    )
    tender_a_id = upload_res.json()["id"]

    # Usuário B tenta deletar edital da Empresa A -> 404
    del_res = client.delete(f"/api/tenders/{tender_a_id}/", HTTP_AUTHORIZATION=f"Bearer {token_b}")
    assert del_res.status_code == 404
    assert del_res.json()["error"]["code"] == "NOT_FOUND"
    assert Tender.objects.filter(id=tender_a_id).exists() is True


def test_idempotent_retry_reproduces_same_tender(client):
    token, _ = create_user_and_token(client, "idem.user@test.com", "Empresa Idempotencia")
    pdf_bytes = b"%PDF-1.4\nIdempotency test payload\n%%EOF"
    key = "idemp-key-001"

    # Primeira requisição com Idempotency-Key
    uploaded_1 = SimpleUploadedFile("edital.pdf", pdf_bytes, content_type="application/pdf")
    res_1 = client.post(
        "/api/tenders/",
        {"file": uploaded_1, "title": "Edital Idempotente"},
        format="multipart",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_IDEMPOTENCY_KEY=key,
    )
    assert res_1.status_code == 202
    tender_id = res_1.json()["id"]

    # Segunda requisição (retry) idêntica com a mesma Idempotency-Key
    uploaded_2 = SimpleUploadedFile("edital.pdf", pdf_bytes, content_type="application/pdf")
    res_2 = client.post(
        "/api/tenders/",
        {"file": uploaded_2, "title": "Edital Idempotente"},
        format="multipart",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_IDEMPOTENCY_KEY=key,
    )
    assert res_2.status_code == 202
    assert res_2.json()["id"] == tender_id

    # Não deve ter criado um segundo edital
    assert Tender.objects.filter(title="Edital Idempotente").count() == 1


def test_idempotent_key_with_different_payload_returns_422(client):
    token, _ = create_user_and_token(client, "conflict.idem@test.com", "Empresa Conflito Idem")
    key = "idemp-key-002"

    pdf_1 = SimpleUploadedFile(
        "edital1.pdf", b"%PDF-1.4\nPayload 1\n%%EOF", content_type="application/pdf"
    )
    res_1 = client.post(
        "/api/tenders/",
        {"file": pdf_1, "title": "Edital 1"},
        format="multipart",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_IDEMPOTENCY_KEY=key,
    )
    assert res_1.status_code == 202

    # Mesma chave com payload alterado (bytes diferentes e título diferente)
    pdf_2 = SimpleUploadedFile(
        "edital2.pdf",
        b"%PDF-1.4\nPayload 2 MODIFICADO\n%%EOF",
        content_type="application/pdf",
    )
    res_2 = client.post(
        "/api/tenders/",
        {"file": pdf_2, "title": "Edital 2 Modificado"},
        format="multipart",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_IDEMPOTENCY_KEY=key,
    )
    assert res_2.status_code == 422
    assert res_2.json()["error"]["code"] == "UNPROCESSABLE_ENTITY"


def test_idempotency_key_is_scoped_by_tenant_and_user(client):
    token_a, _ = create_user_and_token(client, "idem.a@test.com", "Empresa Idem A")
    token_b, _ = create_user_and_token(client, "idem.b@test.com", "Empresa Idem B")
    shared_key = "shared-key-123"

    pdf_a = SimpleUploadedFile(
        "a.pdf", b"%PDF-1.4\nTenant A\n%%EOF", content_type="application/pdf"
    )
    res_a = client.post(
        "/api/tenders/",
        {"file": pdf_a, "title": "Edital A"},
        format="multipart",
        HTTP_AUTHORIZATION=f"Bearer {token_a}",
        HTTP_IDEMPOTENCY_KEY=shared_key,
    )
    assert res_a.status_code == 202

    # Usuário B usa a mesma chave string, mas é outro tenant -> deve ser aceito independentemente
    pdf_b = SimpleUploadedFile(
        "b.pdf", b"%PDF-1.4\nTenant B\n%%EOF", content_type="application/pdf"
    )
    res_b = client.post(
        "/api/tenders/",
        {"file": pdf_b, "title": "Edital B"},
        format="multipart",
        HTTP_AUTHORIZATION=f"Bearer {token_b}",
        HTTP_IDEMPOTENCY_KEY=shared_key,
    )
    assert res_b.status_code == 202
    assert res_a.json()["id"] != res_b.json()["id"]


def test_processing_status_pending(client):
    token, _ = create_user_and_token(client, "status.pending@test.com", "Status Pending SA")
    company = Company.objects.get(name="Status Pending SA")
    tender = Tender.objects.create(
        company=company,
        title="Edital Status Pending",
        status="PENDING",
    )
    res = client.get(
        f"/api/tenders/{tender.id}/processing-status/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert res.status_code == 200
    assert res.headers.get("Retry-After") is not None
    data = res.json()
    assert data["tenderId"] == str(tender.id)
    assert data["status"] == "PENDING"
    assert data["progress"] == 0
    assert data["processedChunks"] == 0
    assert data["error"] is None


def test_processing_status_processing(client):
    token, _ = create_user_and_token(client, "status.proc@test.com", "Status Proc SA")
    company = Company.objects.get(name="Status Proc SA")
    tender = Tender.objects.create(
        company=company,
        title="Edital Status Processing",
        status="PROCESSING",
        progress=65,
        processed_chunks=42,
    )
    res = client.get(
        f"/api/tenders/{tender.id}/processing-status/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert res.status_code == 200
    assert res.headers.get("Retry-After") is not None
    data = res.json()
    assert data["tenderId"] == str(tender.id)
    assert data["status"] == "PROCESSING"
    assert data["progress"] == 65
    assert data["processedChunks"] == 42
    assert data["error"] is None


def test_processing_status_processed(client):
    token, _ = create_user_and_token(client, "status.done@test.com", "Status Done SA")
    company = Company.objects.get(name="Status Done SA")
    tender = Tender.objects.create(
        company=company,
        title="Edital Status Processed",
        status="PROCESSED",
        progress=100,
        processed_chunks=80,
    )
    res = client.get(
        f"/api/tenders/{tender.id}/processing-status/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert res.status_code == 200
    assert res.headers.get("Retry-After") is None
    data = res.json()
    assert data["tenderId"] == str(tender.id)
    assert data["status"] == "PROCESSED"
    assert data["progress"] == 100
    assert data["processedChunks"] == 80
    assert data["error"] is None


def test_processing_status_failed_returns_safe_error(client):
    token, _ = create_user_and_token(client, "status.fail@test.com", "Status Fail SA")
    company = Company.objects.get(name="Status Fail SA")
    tender = Tender.objects.create(
        company=company,
        title="Edital Status Failed",
        status="FAILED",
        error_code="PDF_INVALID",
        error_message="O arquivo PDF está corrompido ou malformado.",
    )
    res = client.get(
        f"/api/tenders/{tender.id}/processing-status/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert res.status_code == 200
    assert res.headers.get("Retry-After") is None
    data = res.json()
    assert data["tenderId"] == str(tender.id)
    assert data["status"] == "FAILED"
    assert data["error"] == {
        "code": "PDF_INVALID",
        "message": "O arquivo PDF está corrompido ou malformado.",
    }


def test_processing_status_cross_tenant_returns_404(client):
    token_a, _ = create_user_and_token(client, "status.a@test.com", "Empresa Status A")
    token_b, _ = create_user_and_token(client, "status.b@test.com", "Empresa Status B")
    company_a = Company.objects.get(name="Empresa Status A")
    tender_a = Tender.objects.create(
        company=company_a,
        title="Edital Tenant A",
        status="PROCESSING",
    )

    res = client.get(
        f"/api/tenders/{tender_a.id}/processing-status/",
        HTTP_AUTHORIZATION=f"Bearer {token_b}",
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


def test_processing_status_unauthenticated_returns_401(client):
    res = client.get(f"/api/tenders/{uuid.uuid4()}/processing-status/")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "AUTHENTICATION_FAILED"



