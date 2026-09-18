"""
OCR de páginas PDF sem camada de texto.

Serviço puro: sem acoplamento com HTTP, Celery ou banco de dados.
Utiliza pypdfium2 para rasterizar a página e pytesseract (Tesseract)
para reconhecer o texto. Se o toolchain não estiver disponível, o
fallback é inofensivo (retorna vazio) e o fluxo existente de
NO_TEXT_EXTRACTED permanece.
"""

import functools
import os

DEFAULT_OCR_LANGUAGE = "por"
DEFAULT_RENDER_SCALE = 300 / 72


def is_ocr_enabled() -> bool:
    return os.environ.get("OCR_ENABLED", "true").strip().lower() not in (
        "false",
        "0",
        "no",
    )


def ocr_language() -> str:
    return os.environ.get("OCR_LANGUAGE", DEFAULT_OCR_LANGUAGE).strip() or DEFAULT_OCR_LANGUAGE


@functools.lru_cache(maxsize=1)
def ocr_available() -> bool:
    """Verifica uma única vez se pypdfium2, pytesseract e o binário Tesseract existem."""
    try:
        import pypdfium2  # noqa: F401
        import pytesseract

        pytesseract.get_tesseract_version()
    except Exception:
        return False
    return True


def ocr_page(
    pdf_bytes: bytes,
    page_index: int,
    language: str = DEFAULT_OCR_LANGUAGE,
    render_scale: float = DEFAULT_RENDER_SCALE,
) -> str:
    """
    Rasteriza a página 0-indexed `page_index` e devolve o texto reconhecido.
    Levanta exceção se o toolchain de OCR não estiver disponível.
    """
    import pypdfium2 as pdfium
    import pytesseract

    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        page = pdf[page_index]
        bitmap = page.render(scale=render_scale)
        image = bitmap.to_pil()
    finally:
        pdf.close()

    return pytesseract.image_to_string(image, lang=language)
