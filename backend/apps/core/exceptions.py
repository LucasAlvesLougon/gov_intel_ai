import logging

from django.http import JsonResponse
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler

logger = logging.getLogger("django.request")


class ConflictError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflito de recursos."
    default_code = "CONFLICT"


class UnprocessableEntityError(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Erro de validação semântica."
    default_code = "UNPROCESSABLE_ENTITY"


def custom_exception_handler(exc, context):
    """
    Handler global que padroniza todas as respostas de erro HTTP no envelope comum:
    {
      "error": {
        "code": "...",
        "message": "...",
        "details": {}
      }
    }
    Cobre: 400, 401, 403, 404, 409, 422, 429 e 500 (sem vazar detalhes de infraestrutura).
    """
    response = exception_handler(exc, context)
    if response is not None:
        code = "API_ERROR"
        message = "Ocorreu um erro ao processar a requisição."
        details = {}

        if response.status_code == 400:
            code = "VALIDATION_ERROR"
            message = "Dados da requisição inválidos."
            if isinstance(response.data, dict) and "detail" in response.data:
                details = {"non_field_errors": [str(response.data["detail"])]}
            elif isinstance(response.data, dict):
                details = response.data
            else:
                details = {"non_field_errors": response.data}
        elif response.status_code == 401:
            code = "AUTHENTICATION_FAILED"
            message = "Credenciais inválidas ou token ausente/expirado."
        elif response.status_code == 403:
            code = "PERMISSION_DENIED"
            message = "Você não tem permissão para acessar este recurso."
        elif response.status_code == 404:
            code = "NOT_FOUND"
            message = "Recurso não encontrado."
        elif response.status_code == 409:
            code = "CONFLICT"
            if isinstance(response.data, dict):
                message = response.data.get("detail", "Email já cadastrado.")
            else:
                message = str(response.data)
        elif response.status_code == 422:
            code = "UNPROCESSABLE_ENTITY"
            if isinstance(response.data, dict):
                message = response.data.get("detail", "Erro de validação semântica.")
            else:
                message = str(response.data)
        elif response.status_code == 429:
            code = "RATE_LIMITED"
            message = "Muitas requisições. Tente novamente mais tarde."
            details = {}
            if hasattr(exc, "wait") and exc.wait is not None:
                response["Retry-After"] = str(int(exc.wait) if exc.wait > 0 else 1)
        elif response.status_code == 500:
            code = "INTERNAL_SERVER_ERROR"
            message = "Erro interno do servidor."
            details = {}
        else:
            code = getattr(exc, "default_code", "ERROR").upper()
            message = str(getattr(exc, "detail", "Erro ao processar requisição."))

        response.data = {
            "error": {
                "code": code,
                "message": str(message),
                "details": details,
            }
        }
        return response

    return None


def custom_handler404(request, exception=None):
    """Handler global para 404 fora do escopo de views DRF."""
    return JsonResponse(
        {
            "error": {
                "code": "NOT_FOUND",
                "message": "Recurso não encontrado.",
                "details": {},
            }
        },
        status=404,
    )


def custom_handler500(request):
    """Handler global para 500 fora do escopo de views DRF."""
    logger.exception("Erro 500 não tratado no nível do Django.")
    return JsonResponse(
        {
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Erro interno do servidor.",
                "details": {},
            }
        },
        status=500,
    )
