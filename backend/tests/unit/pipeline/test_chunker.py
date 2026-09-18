from apps.pipeline.chunker import create_chunks_from_pages
from apps.pipeline.pdf_extractor import ExtractedPage


def _page(text: str, page_number: int = 1, start: int = 0) -> ExtractedPage:
    return ExtractedPage(
        page_number=page_number,
        text=text,
        char_count=len(text),
        start_char_offset=start,
        end_char_offset=start + len(text),
    )


def test_chunks_end_at_sentence_boundaries():
    sentences = [
        f"Cláusula {i} estabelece condições detalhadas de execução do objeto "
        f"contratado conforme termo de referência anexo número {i}."
        for i in range(1, 15)
    ]
    page = _page(" ".join(sentences))

    chunks = create_chunks_from_pages([page], target_chunk_size=800, chunk_overlap=100)

    assert len(chunks) > 1
    for chunk in chunks[:-1]:
        # Nenhum chunk (exceto o último) termina no meio de uma frase
        assert chunk.text[-1] in ".!?"


def test_single_sentence_longer_than_target_is_hard_cut():
    long_sentence = "palavra " * 400  # ~2800 caracteres sem pontuação interna
    page = _page(long_sentence.strip())

    chunks = create_chunks_from_pages([page], target_chunk_size=800, chunk_overlap=100)

    assert len(chunks) >= 3
    assert all(len(chunk.text) <= 800 for chunk in chunks)


def test_chunk_offsets_and_overlap_preserved():
    sentences = [
        f"Sentença número {i} contém conteúdo suficiente para ocupar espaço "
        f"considerável dentro do documento do edital em análise constante {i}."
        for i in range(1, 15)
    ]
    text = " ".join(sentences)
    page = _page(text, start=5000)

    chunks = create_chunks_from_pages([page], target_chunk_size=800, chunk_overlap=100)

    assert all(c.start_char_offset >= 5000 for c in chunks)
    assert all(c.end_char_offset > c.start_char_offset for c in chunks)
    # Sobreposição: chunks consecutivos se sobrepõem no texto original
    for prev, nxt in zip(chunks, chunks[1:], strict=False):
        assert nxt.start_char_offset < prev.end_char_offset
    # Hash corresponde ao texto do chunk
    for chunk in chunks:
        import hashlib

        assert chunk.text_hash == hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
