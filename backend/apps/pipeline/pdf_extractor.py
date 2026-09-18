import io
import logging
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from typing import BinaryIO

from pypdf import PdfReader

from apps.pipeline import ocr as ocr_module
from apps.pipeline.exceptions import (
    CharLimitExceededError,
    NoTextExtractedError,
    PageLimitExceededError,
    PdfEncryptedError,
    PdfInvalidError,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_PAGES = 1000
DEFAULT_MAX_CHARS = 2_000_000

OcrFn = Callable[[bytes, int], str]


def _default_ocr_fn(pdf_bytes: bytes, page_index: int) -> str:
    """
    Fallback gracioso: OCR desabilitado, toolchain ausente ou falha de
    reconhecimento deixam a página vazia, preservando o comportamento
    de NO_TEXT_EXTRACTED quando nenhuma página produzir texto.
    """
    if not ocr_module.is_ocr_enabled() or not ocr_module.ocr_available():
        return ""
    return ocr_module.ocr_page(pdf_bytes, page_index, ocr_module.ocr_language())


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int  # 1-indexed
    text: str
    char_count: int
    start_char_offset: int
    end_char_offset: int


def normalize_page_text(text: str) -> str:
    """Normaliza o texto extraído da página usando NFKC e limpando whitespace redundante."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    # Uniformizar quebras de linha
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    # Remover espaços em branco no fim de cada linha
    lines = [line.strip() for line in normalized.split("\n")]
    # Remover múltiplas linhas vazias consecutivas
    cleaned_lines = []
    prev_empty = False
    for line in lines:
        if not line:
            if not prev_empty:
                cleaned_lines.append("")
                prev_empty = True
        else:
            cleaned_lines.append(line)
            prev_empty = False
    return "\n".join(cleaned_lines).strip()


def _compact_layout_columns(text: str) -> str:
    """
    No modo layout, colunas de tabelas chegam como sequências longas de
    espaços. Colapsá-las em ' | ' preserva a estrutura visual da tabela
    para o chunking e o RAG sem poluir o texto corrido.
    """
    lines = [re.sub(r" {2,}", " | ", line).strip() for line in text.split("\n")]
    return "\n".join(lines)


def extract_pdf_pages(
    source: bytes | BinaryIO,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_chars: int = DEFAULT_MAX_CHARS,
    ocr_fn: OcrFn | None = _default_ocr_fn,
) -> list[ExtractedPage]:
    """
    Serviço puro de extração de texto por página a partir de dados PDF.
    Não possui acoplamento com HTTP, Celery ou banco de dados.
    Páginas sem camada de texto passam por OCR quando disponível (`ocr_fn`);
    passe `ocr_fn=None` para desativar explicitamente o OCR.
    """
    if isinstance(source, bytes):
        data = source
    else:
        data = source.read()
    stream = io.BytesIO(data)

    try:
        reader = PdfReader(stream)
    except Exception as exc:
        raise PdfInvalidError(f"Falha ao ler estrutura do PDF: {exc}") from exc

    if reader.is_encrypted:
        try:
            # Tentar desencriptar sem senha se for uma criptografia vazia padrão
            decrypt_result = reader.decrypt("")
            if decrypt_result == 0 and reader.is_encrypted:
                raise PdfEncryptedError()
        except Exception as exc:
            raise PdfEncryptedError() from exc

    try:
        total_pages = len(reader.pages)
    except Exception as exc:
        raise PdfInvalidError(f"Falha ao obter páginas do PDF: {exc}") from exc

    if total_pages > max_pages:
        raise PageLimitExceededError(
            f"O documento possui {total_pages} páginas, excedendo o limite de {max_pages}."
        )

    extracted_pages: list[ExtractedPage] = []
    current_offset = 0
    total_chars = 0

    for idx, page in enumerate(reader.pages):
        page_num = idx + 1
        # Modo layout preserva colunas de tabelas; sem fonte/estrutura
        # esperada, cai para o modo normal.
        try:
            raw_text = _compact_layout_columns(
                page.extract_text(extraction_mode="layout") or ""
            )
        except Exception:
            try:
                raw_text = page.extract_text() or ""
            except Exception as exc:
                raise PdfInvalidError(
                    f"Falha ao extrair texto da página {page_num}: {exc}"
                ) from exc

        page_text = normalize_page_text(raw_text)

        # Página sem camada de texto (ex.: PDF escaneado): tentar OCR
        if not page_text and ocr_fn is not None:
            try:
                ocr_text = ocr_fn(data, idx)
            except Exception:
                logger.warning(
                    "OCR falhou para a pagina %d; seguindo sem texto desta pagina.",
                    page_num,
                )
                ocr_text = ""
            page_text = normalize_page_text(ocr_text or "")

        page_char_count = len(page_text)
        total_chars += page_char_count

        if total_chars > max_chars:
            raise CharLimitExceededError(
                f"O documento excede o limite máximo de {max_chars} caracteres."
            )

        start_offset = current_offset
        end_offset = current_offset + page_char_count

        extracted_pages.append(
            ExtractedPage(
                page_number=page_num,
                text=page_text,
                char_count=page_char_count,
                start_char_offset=start_offset,
                end_char_offset=end_offset,
            )
        )
        current_offset = end_offset

    # Se todos os caracteres extraídos forem vazios, documento é considerado sem texto
    if total_chars == 0:
        raise NoTextExtractedError()

    return extracted_pages
