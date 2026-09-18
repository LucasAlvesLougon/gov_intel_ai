import logging

from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import Throttled
from rest_framework.throttling import SimpleRateThrottle

logger = logging.getLogger("django.request")


class BaseGovIntelThrottle(SimpleRateThrottle):
    """
    Classe base para throttling backed por Redis.
    Formato de chave canônico segundo docs/api-contract.md:
    govintel:v1:throttle:{ident}:{endpoint}
    """

    cache = cache

    def get_rate(self):
        # Permite resolução dinâmica e compatibilidade com override_settings nos testes
        drf_settings = getattr(settings, "REST_FRAMEWORK", {})
        rates = drf_settings.get("DEFAULT_THROTTLE_RATES", {})
        if self.scope in rates:
            return rates[self.scope]
        return super().get_rate()

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = str(request.user.id)
        else:
            ident = self.get_ident(request)
        return f"govintel:v1:throttle:{ident}:{self.scope}"

    def allow_request(self, request, view):
        try:
            return super().allow_request(request, view)
        except Exception as exc:
            # Throttling fail-open permitiria contornar todos os limites quando o
            # Redis estivesse indisponível. Bloqueie com erro genérico e audite só
            # o tipo da falha, sem expor a conexão ou a chave de cache.
            logger.warning(
                "Falha na checagem de throttling por erro de cache: %s",
                type(exc).__name__,
            )
            raise Throttled(
                wait=int(getattr(settings, "THROTTLE_FAIL_CLOSED_WAIT", 60))
            ) from exc


class LoginThrottle(BaseGovIntelThrottle):
    """
    Throttling para endpoint de login (POST /api/auth/token/).
    Escopado por IP do cliente.
    Chave: govintel:v1:throttle:{ip}:login
    """

    scope = "login"

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return f"govintel:v1:throttle:{ident}:{self.scope}"


class RegisterThrottle(LoginThrottle):
    """Limita criação de contas por endereço remoto confiável."""

    scope = "register"


class RefreshThrottle(LoginThrottle):
    """Limita tentativas de refresh por endereço remoto confiável."""

    scope = "refresh"


class SearchThrottle(BaseGovIntelThrottle):
    """
    Throttling para endpoint de busca semântica (POST /api/search/semantic/).
    Escopado pelo ID do usuário autenticado.
    Chave: govintel:v1:throttle:{userId}:search
    """

    scope = "search"


class ChatThrottle(BaseGovIntelThrottle):
    """
    Throttling para endpoint de RAG chat (POST /api/tenders/{id}/chat/).
    Escopado pelo ID do usuário autenticado.
    Chave: govintel:v1:throttle:{userId}:chat
    """

    scope = "chat"


class UploadThrottle(BaseGovIntelThrottle):
    """Limita uploads pelo usuário autenticado e pelo tenant derivado no backend."""

    scope = "upload"
