import hashlib

from rest_framework.exceptions import ValidationError

DEFAULT_MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB


def validate_pdf_upload(
    uploaded_file,
    max_size: int = DEFAULT_MAX_UPLOAD_SIZE,
) -> tuple[bytes, str]:
    """
    Valida se o arquivo enviado é um PDF seguro, não vazio e dentro do tamanho permitido.
    Retorna os bytes lidos e o hash sha256.
    """
    if not uploaded_file:
        raise ValidationError({"file": "O arquivo PDF é obrigatório."})

    if uploaded_file.size is not None and uploaded_file.size == 0:
        raise ValidationError({"file": "O arquivo enviado está vazio."})

    if uploaded_file.size is not None and uploaded_file.size > max_size:
        raise ValidationError(
            {"file": f"O arquivo excede o tamanho máximo permitido de {max_size} bytes."}
        )

    file_bytes = uploaded_file.read()
    if not file_bytes:
        raise ValidationError({"file": "O arquivo enviado está vazio."})

    if len(file_bytes) > max_size:
        raise ValidationError(
            {"file": f"O arquivo excede o tamanho máximo permitido de {max_size} bytes."}
        )

    # Verificação de magic bytes (assinatura do cabeçalho PDF)
    if not file_bytes.startswith(b"%PDF-"):
        raise ValidationError(
            {"file": "O arquivo fornecido não possui assinatura válida de PDF (%PDF-)."}
        )

    sha256_hash = hashlib.sha256(file_bytes).hexdigest()
    return file_bytes, sha256_hash
