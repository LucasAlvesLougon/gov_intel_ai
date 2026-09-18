import hashlib
import re
from dataclasses import dataclass

from apps.pipeline.pdf_extractor import ExtractedPage

_SENTENCE_BOUNDARY = re.compile(r"[.!?](?=\s|$)|\n")


def _snap_end_to_sentence(text: str, start: int, end: int, min_len: int) -> int:
    """
    Ajusta o corte do chunk para o fim da última frase completa dentro da
    janela [start, end). Frases longer que a janela inteira sofrem corte duro.
    """
    window = text[start:end]
    best = -1
    for match in _SENTENCE_BOUNDARY.finditer(window):
        if match.end() >= min_len:
            best = match.end()
    if best <= 0:
        return end
    return start + best


@dataclass(frozen=True)
class ChunkPayload:
    chunk_index: int
    page_number: int
    start_char_offset: int
    end_char_offset: int
    text: str
    text_hash: str


def create_chunks_from_pages(
    pages: list[ExtractedPage],
    target_chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> list[ChunkPayload]:
    """Divide as páginas extraídas em chunks preservando página e offsets exatos."""
    chunks: list[ChunkPayload] = []
    chunk_index = 0

    for page in pages:
        text = page.text
        if not text:
            continue

        if len(text) <= target_chunk_size:
            text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            chunks.append(
                ChunkPayload(
                    chunk_index=chunk_index,
                    page_number=page.page_number,
                    start_char_offset=page.start_char_offset,
                    end_char_offset=page.end_char_offset,
                    text=text,
                    text_hash=text_hash,
                )
            )
            chunk_index += 1
            continue

        start = 0
        text_len = len(text)
        min_len = max(1, target_chunk_size // 2)

        while start < text_len:
            end = min(start + target_chunk_size, text_len)
            if end < text_len:
                end = _snap_end_to_sentence(text, start, end, min_len)
            chunk_slice = text[start:end].strip()

            if chunk_slice:
                text_hash = hashlib.sha256(chunk_slice.encode("utf-8")).hexdigest()
                chunks.append(
                    ChunkPayload(
                        chunk_index=chunk_index,
                        page_number=page.page_number,
                        start_char_offset=page.start_char_offset + start,
                        end_char_offset=page.start_char_offset + end,
                        text=chunk_slice,
                        text_hash=text_hash,
                    )
                )
                chunk_index += 1

            if end >= text_len:
                break
            start = max(end - chunk_overlap, start + 1)

    return chunks
