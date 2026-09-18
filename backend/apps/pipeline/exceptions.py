SAFE_PIPELINE_ERROR_MESSAGES = {
    "PDF_INVALID": "O arquivo PDF está corrompido ou malformado.",
    "PDF_ENCRYPTED": "O arquivo PDF está protegido por senha e não pôde ser lido.",
    "NO_TEXT_EXTRACTED": "Nenhum texto pôde ser extraído do documento PDF.",
    "PAGE_LIMIT_EXCEEDED": "O documento excede o limite máximo de páginas permitido.",
    "CHAR_LIMIT_EXCEEDED": "O documento excede o limite máximo de caracteres permitido.",
    "PROCESSING_TIMEOUT": "O processamento do edital expirou e será tentado novamente.",
    "PROCESSING_FAILED": "Falha no processamento do edital.",
}


def safe_pipeline_error_message(code: str | None) -> str:
    return SAFE_PIPELINE_ERROR_MESSAGES.get(
        code or "", SAFE_PIPELINE_ERROR_MESSAGES["PROCESSING_FAILED"]
    )


def safe_pipeline_storage_message(code: str | None) -> str:
    """Mensagem segura persistida no registro interno do pipeline."""
    if code == "PDF_INVALID":
        return SAFE_PIPELINE_ERROR_MESSAGES["PROCESSING_FAILED"]
    return safe_pipeline_error_message(code)


class PipelineDomainError(Exception):
    """Exceção base para erros de domínio do pipeline."""

    def __init__(self, message: str, code: str = "PIPELINE_ERROR"):
        super().__init__(message)
        self.code = code
        self.message = message


class PdfInvalidError(PipelineDomainError):
    def __init__(self, message: str = "O arquivo PDF é inválido ou está corrompido."):
        super().__init__(message, code="PDF_INVALID")


class PdfEncryptedError(PipelineDomainError):
    def __init__(
        self,
        message: str = "O arquivo PDF está protegido por senha e não pôde ser lido.",
    ):
        super().__init__(message, code="PDF_ENCRYPTED")


class NoTextExtractedError(PipelineDomainError):
    def __init__(
        self, message: str = "Nenhum texto pôde ser extraído do documento PDF."
    ):
        super().__init__(message, code="NO_TEXT_EXTRACTED")


class PageLimitExceededError(PipelineDomainError):
    def __init__(
        self,
        message: str = "O documento excede o limite máximo de páginas permitido.",
    ):
        super().__init__(message, code="PAGE_LIMIT_EXCEEDED")


class CharLimitExceededError(PipelineDomainError):
    def __init__(
        self,
        message: str = "O documento excede o limite máximo de caracteres permitido.",
    ):
        super().__init__(message, code="CHAR_LIMIT_EXCEEDED")
