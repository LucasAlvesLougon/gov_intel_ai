import pytest

from apps.pipeline import ocr as ocr_module
from apps.pipeline.exceptions import NoTextExtractedError
from apps.pipeline.pdf_extractor import extract_pdf_pages
from tests.fixtures.pdf_helpers import (
    create_mixed_text_and_scanned_pdf,
    create_scanned_pdf,
)


def test_ocr_recovers_text_from_scanned_pdf():
    pdf_bytes = create_scanned_pdf(["Prazo de entrega: 30 dias corridos"])

    pages = extract_pdf_pages(pdf_bytes)

    assert len(pages) == 1
    assert "Prazo de entrega" in pages[0].text
    assert "30 dias" in pages[0].text


def test_mixed_pdf_uses_text_layer_and_ocr_only_for_scanned_page():
    pdf_bytes = create_mixed_text_and_scanned_pdf(
        "Objeto: Aquisicao de equipamentos medicos.",
        "Garantia minima de 12 meses.",
    )

    pages = extract_pdf_pages(pdf_bytes)

    assert len(pages) == 2
    assert "Aquisicao de equipamentos medicos" in pages[0].text
    assert "Garantia minima" in pages[1].text


def test_ocr_disabled_by_env_raises_no_text_extracted(monkeypatch):
    monkeypatch.setenv("OCR_ENABLED", "false")
    pdf_bytes = create_scanned_pdf(["Prazo de entrega: 30 dias corridos"])

    with pytest.raises(NoTextExtractedError) as exc_info:
        extract_pdf_pages(pdf_bytes)
    assert exc_info.value.code == "NO_TEXT_EXTRACTED"


def test_ocr_function_can_be_injected():
    pdf_bytes = create_mixed_text_and_scanned_pdf(
        "Pagina textual original.",
        "Pagina escaneada sem camada de texto.",
    )
    calls: list[int] = []

    def fake_ocr(data: bytes, page_index: int) -> str:
        calls.append(page_index)
        return "Texto recuperado via OCR simulado."

    pages = extract_pdf_pages(pdf_bytes, ocr_fn=fake_ocr)

    assert calls == [1]
    assert "Pagina textual original" in pages[0].text
    assert "Texto recuperado via OCR simulado" in pages[1].text


def test_ocr_failure_degrades_to_no_text_extracted():
    pdf_bytes = create_scanned_pdf(["Prazo de entrega: 30 dias corridos"])

    def failing_ocr(data: bytes, page_index: int) -> str:
        raise RuntimeError("tesseract indisponivel")

    with pytest.raises(NoTextExtractedError) as exc_info:
        extract_pdf_pages(pdf_bytes, ocr_fn=failing_ocr)
    assert exc_info.value.code == "NO_TEXT_EXTRACTED"


def test_ocr_toolchain_detection_reflects_availability():
    assert isinstance(ocr_module.ocr_available(), bool)
    assert isinstance(ocr_module.is_ocr_enabled(), bool)
