from django.db import DatabaseError, connection
from django.http import JsonResponse


def health(request):
    if request.method != "GET":
        return JsonResponse(
            {"error": {"code": "METHOD_NOT_ALLOWED", "message": "Método inválido.", "details": {}}},
            status=405,
            headers={"Allow": "GET"},
        )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse(
            {
                "error": {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "Serviço temporariamente indisponível.",
                    "details": {},
                }
            },
            status=503,
        )
    return JsonResponse({"status": "ok"})
