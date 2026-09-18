import pytest

from apps.pipeline.exceptions import (
    CharLimitExceededError,
    NoTextExtractedError,
    PageLimitExceededError,
    PdfEncryptedError,
    PdfInvalidError,
)
from apps.pipeline.pdf_extractor import ExtractedPage, extract_pdf_pages
from tests.fixtures.pdf_helpers import (
    create_blank_pdf,
    create_encrypted_pdf,
    create_minimal_text_pdf,
    create_table_pdf,
)


def test_table_pdf_preserves_columns_per_row():
    pdf_bytes = create_table_pdf(
        [
            ["Item", "Quantidade", "Valor"],
            ["Cadeira", "100", "R$ 50.000,00"],
            ["Mesa", "20", "R$ 30.000,00"],
        ]
    )

    pages = extract_pdf_pages(pdf_bytes)

    text = pages[0].text
    lines = text.split("\n")
    header_line = next(line for line in lines if "Item" in line)
    cadeira_line = next(line for line in lines if "Cadeira" in line)
    mesa_line = next(line for line in lines if "Mesa" in line)

    # Colunas preservadas com separador explícito (modo layout)
    assert header_line == "Item | Quantidade | Valor"
    assert cadeira_line == "Cadeira | 100 | R$ 50.000,00"
    assert mesa_line == "Mesa | 20 | R$ 30.000,00"


def test_layout_mode_failure_falls_back_to_normal_text(monkeypatch):
    import pypdf

    from apps.pipeline import pdf_extractor as extractor_module

    class FakePage:
        def extract_text(self, extraction_mode=None):
            if extraction_mode == "layout":
                raise pypdf.errors.PdfReadError("font not set")
            return "Texto corrido em modo normal."

    class FakeReader:
        is_encrypted = False

        def __init__(self, stream):
            pass

        @property
        def pages(self):
            return [FakePage()]

    monkeypatch.setattr(extractor_module, "PdfReader", FakeReader)

    pages = extract_pdf_pages(b"pdf qualquer")

    assert "Texto corrido em modo normal." == pages[0].text


def test_extract_text_multi_page_fixture():
    pages_input = [
        "Objeto: Aquisicao de equipamentos medicos e hospitalares.",
        "Especificacoes tecnicas: Tomografo computadorizado 64 canais.",
    ]
    pdf_bytes = create_minimal_text_pdf(pages_input)

    pages = extract_pdf_pages(pdf_bytes)

    assert len(pages) == 2
    assert all(isinstance(p, ExtractedPage) for p in pages)

    page_1 = pages[0]
    assert page_1.page_number == 1
    assert "Aquisicao de equipamentos medicos" in page_1.text
    assert page_1.start_char_offset == 0
    assert page_1.end_char_offset == len(page_1.text)
    assert page_1.char_count == len(page_1.text)

    page_2 = pages[1]
    assert page_2.page_number == 2
    assert "Tomografo computadorizado" in page_2.text
    assert page_2.start_char_offset == page_1.end_char_offset
    assert page_2.end_char_offset == page_2.start_char_offset + len(page_2.text)


def test_extract_text_empty_pdf_raises_no_text_extracted():
    blank_pdf = create_blank_pdf(num_pages=2)
    with pytest.raises(NoTextExtractedError) as exc_info:
        extract_pdf_pages(blank_pdf)
    assert exc_info.value.code == "NO_TEXT_EXTRACTED"


def test_extract_text_encrypted_pdf_raises_pdf_encrypted():
    encrypted_pdf = create_encrypted_pdf("Segredo", "senha123")
    with pytest.raises(PdfEncryptedError) as exc_info:
        extract_pdf_pages(encrypted_pdf)
    assert exc_info.value.code == "PDF_ENCRYPTED"


def test_extract_text_corrupted_pdf_raises_pdf_invalid():
    corrupted_bytes = b"%PDF-1.4\nCorrupted content without valid objects or xref"
    with pytest.raises(PdfInvalidError) as exc_info:
        extract_pdf_pages(corrupted_bytes)
    assert exc_info.value.code == "PDF_INVALID"


def test_extract_text_page_limit_exceeded():
    pdf_bytes = create_minimal_text_pdf(["Page 1", "Page 2", "Page 3"])
    with pytest.raises(PageLimitExceededError) as exc_info:
        extract_pdf_pages(pdf_bytes, max_pages=2)
    assert exc_info.value.code == "PAGE_LIMIT_EXCEEDED"


def test_extract_text_char_limit_exceeded():
    pdf_bytes = create_minimal_text_pdf(["Texto longo que ultrapassa limite"])
    with pytest.raises(CharLimitExceededError) as exc_info:
        extract_pdf_pages(pdf_bytes, max_chars=10)
    assert exc_info.value.code == "CHAR_LIMIT_EXCEEDED"


def test_service_has_no_http_or_celery_dependencies():
    import apps.pipeline.pdf_extractor as extractor_module

    with open(extractor_module.__file__, encoding="utf-8") as f:
        source = f.read()
    assert "rest_framework" not in source
    assert "django.http" not in source
    assert "celery" not in source
    assert "Response" not in source
    assert "status.HTTP" not in source
