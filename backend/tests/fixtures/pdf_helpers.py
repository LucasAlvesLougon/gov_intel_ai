import io

from pypdf import PdfReader, PdfWriter


def create_minimal_text_pdf(pages: list[str]) -> bytes:
    """Gera um PDF textual válido em memória com N páginas."""
    objects = []
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

    kids = " ".join(f"{3 + i * 2} 0 R" for i in range(len(pages)))
    objects.append(
        f"2 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>\nendobj\n".encode()
    )

    for i, page_text in enumerate(pages):
        page_obj_num = 3 + i * 2
        content_obj_num = 4 + i * 2

        # Sanitize text for basic PDF latin-1 stream
        safe_text = page_text.replace("(", r"\(").replace(")", r"\)")
        stream_content = f"BT\n/F1 12 Tf\n72 712 Td\n({safe_text}) Tj\nET\n".encode(
            "latin-1", errors="replace"
        )
        length = len(stream_content)

        page_obj = (
            f"{page_obj_num} 0 obj\n"
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_obj_num} 0 R /Resources << /Font << /F1 100 0 R >> >> >>\n"
            f"endobj\n"
        ).encode()
        objects.append(page_obj)

        content_obj = (
            f"{content_obj_num} 0 obj\n<< /Length {length} >>\nstream\n".encode()
            + stream_content
            + b"endstream\nendobj\n"
        )
        objects.append(content_obj)

    font_obj = b"100 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    objects.append(font_obj)

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)

    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())

    trailer = f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF"
    out.extend(trailer.encode())
    return bytes(out)


def create_blank_pdf(num_pages: int = 1) -> bytes:
    """Gera um PDF válido sem nenhum texto (páginas em branco)."""
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def create_encrypted_pdf(text: str = "Secret Tender Content", password: str = "secret") -> bytes:
    """Gera um PDF criptografado protegido por senha."""
    base_pdf = create_minimal_text_pdf([text])
    reader = PdfReader(io.BytesIO(base_pdf))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(password)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def create_scanned_pdf(page_texts: list[str]) -> bytes:
    """
    Gera um PDF "escaneado": cada página é apenas uma imagem rasterizada com o
    texto desenhado, sem camada de texto extraível.
    """
    from PIL import Image, ImageDraw, ImageFont

    page_width, page_height = 1240, 1754
    images = []
    for text in page_texts:
        image = Image.new("RGB", (page_width, page_height), "white")
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 40)
        except OSError:
            font = ImageFont.load_default(size=40)
        draw.text((100, 160), text, fill="black", font=font)
        images.append(image)

    buf = io.BytesIO()
    images[0].save(buf, format="PDF", save_all=True, append_images=images[1:])
    return buf.getvalue()


def create_table_pdf(rows: list[list[str]]) -> bytes:
    """
    Gera um PDF com uma "tabela" desenhada por posicionamento espacial de
    células (Tm), sem linhas de grade — simula tabelas de editais.
    """
    objects = []
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    objects.append(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
    )
    parts = []
    y = 700
    for row in rows:
        x = 72
        for cell in row:
            safe_cell = cell.replace("(", r"\(").replace(")", r"\)")
            parts.append(f"BT /F1 12 Tf 1 0 0 1 {x} {y} Tm ({safe_cell}) Tj ET")
            x += 150
        y -= 20
    stream_content = "\n".join(parts).encode("latin-1", errors="replace")
    objects.append(
        b"4 0 obj\n<< /Length " + str(len(stream_content)).encode() + b" >>\nstream\n"
        + stream_content
        + b"\nendstream\nendobj\n"
    )
    objects.append(
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    )

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    trailer = f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF"
    out.extend(trailer.encode())
    return bytes(out)


def create_mixed_text_and_scanned_pdf(text_page: str, scanned_page: str) -> bytes:
    """Gera um PDF com uma página textual seguida de uma página escaneada."""
    text_pdf = PdfReader(io.BytesIO(create_minimal_text_pdf([text_page])))
    scanned_pdf = PdfReader(io.BytesIO(create_scanned_pdf([scanned_page])))

    writer = PdfWriter()
    for page in text_pdf.pages:
        writer.add_page(page)
    for page in scanned_pdf.pages:
        writer.add_page(page)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()
