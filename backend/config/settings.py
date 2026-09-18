import os
from datetime import timedelta
from pathlib import Path

from kombu import Exchange, Queue

from .environment import (
    configured_embedding_provider,
    configured_llm_provider,
    database_config,
    embedding_dimensions,
    required,
)

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = required("DJANGO_SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,api").split(",")
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "apps.core",
    "apps.tenders",
    "apps.pipeline",
    "apps.intelligence",
    "apps.conversations",
]
AUTH_USER_MODEL = "core.User"
AUTHENTICATION_BACKENDS = [
    "apps.core.backends.CaseInsensitiveModelBackend",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "corsheaders.middleware.CorsMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {"default": database_config()}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "UTC"
USE_TZ = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0
CSRF_COOKIE_HTTPONLY = True
FRONTEND_ORIGIN = required("FRONTEND_ORIGIN")

# Permite mais de uma origem explicitamente configurada (por exemplo,
# localhost e 127.0.0.1 no ambiente local), mantendo CORS e CSRF alinhados.
_configured_frontend_origins = os.environ.get("FRONTEND_ORIGINS", "")
FRONTEND_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in _configured_frontend_origins.split(",")
    if origin.strip()
]
if FRONTEND_ORIGIN not in FRONTEND_ORIGINS:
    FRONTEND_ORIGINS.insert(0, FRONTEND_ORIGIN)
CSRF_TRUSTED_ORIGINS = FRONTEND_ORIGINS

# CORS restrito às origens configuradas; nunca wildcard com credenciais.
CORS_ALLOWED_ORIGINS = FRONTEND_ORIGINS
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "x-csrftoken",
    "idempotency-key",
    "origin",
]
CORS_ALLOW_METHODS = [
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "OPTIONS",
]
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "login": os.environ.get("THROTTLE_RATE_LOGIN", "5/minute"),
        "register": os.environ.get("THROTTLE_RATE_REGISTER", "5/minute"),
        "refresh": os.environ.get("THROTTLE_RATE_REFRESH", "20/minute"),
        "upload": os.environ.get("THROTTLE_RATE_UPLOAD", "10/minute"),
        "search": os.environ.get("THROTTLE_RATE_SEARCH", "30/minute"),
        "chat": os.environ.get("THROTTLE_RATE_CHAT", "15/minute"),
    },
    # Por padrão nenhum proxy é confiável; configurar explicitamente apenas
    # quando houver um reverse proxy sob controle da implantação.
    "NUM_PROXIES": int(os.environ.get("TRUSTED_PROXY_COUNT", "0")),
    "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
}
THROTTLE_FAIL_CLOSED_WAIT = int(os.environ.get("THROTTLE_FAIL_CLOSED_WAIT", "60"))
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": required("REDIS_URL"),
        "TIMEOUT": 300,
        "OPTIONS": {"socket_connect_timeout": 3, "socket_timeout": 3},
    }
}
SEARCH_CACHE_TTL = int(os.environ.get("SEARCH_CACHE_TTL", 300))
LLM_PROVIDER = configured_llm_provider()
EMBEDDING_PROVIDER = configured_embedding_provider()
EMBEDDING_DIMENSIONS = embedding_dimensions()
LOCAL_EMBEDDING_MODEL = os.environ.get(
    "LOCAL_EMBEDDING_MODEL", "intfloat/multilingual-e5-base"
)
LOCAL_EMBEDDING_DEVICE = os.environ.get("LOCAL_EMBEDDING_DEVICE", "cpu")
LOCAL_EMBEDDING_BATCH_SIZE = int(os.environ.get("LOCAL_EMBEDDING_BATCH_SIZE", "32"))
LOCAL_EMBEDDING_REVISION = os.environ.get("LOCAL_EMBEDDING_REVISION", "main")
LOCAL_EMBEDDING_CACHE_DIR = os.environ.get("LOCAL_EMBEDDING_CACHE_DIR", "")
GEMINI_EMBEDDING_MODEL = os.environ.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")
OPENCODE_API_KEY = os.environ.get("OPENCODE_API_KEY", "")
OPENCODE_BASE_URL = os.environ.get(
    "OPENCODE_BASE_URL", "https://opencode.ai/zen/v1"
)
OPENCODE_CHAT_MODEL = os.environ.get("OPENCODE_CHAT_MODEL", "deepseek-v4-flash")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.environ.get(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
)
OPENROUTER_LLM_MODEL = os.environ.get("OPENROUTER_LLM_MODEL", "xiaomi/mimo-v2.5")
OPENROUTER_EMBEDDING_MODEL = os.environ.get(
    "OPENROUTER_EMBEDDING_MODEL", "openai/text-embedding-3-small"
)
CELERY_BROKER_URL = required("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = required("CELERY_RESULT_BACKEND")
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_CONNECTION_TIMEOUT = 5
CELERY_BROKER_TRANSPORT_OPTIONS = {"confirm_publish": True}
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_DEFAULT_QUEUE = "govintel.pipeline"
CELERY_TASK_DEFAULT_EXCHANGE = "govintel"
CELERY_TASK_DEFAULT_ROUTING_KEY = "pipeline"
CELERY_TASK_DEFAULT_DELIVERY_MODE = "persistent"
CELERY_TASK_CREATE_MISSING_QUEUES = False
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_SOFT_TIME_LIMIT = 240
CELERY_TASK_TIME_LIMIT = 270
CELERY_TASK_QUEUES = (
    Queue(
        "govintel.pipeline",
        Exchange("govintel", type="direct", durable=True),
        routing_key="pipeline",
        durable=True,
        queue_arguments={
            "x-dead-letter-exchange": "govintel.dead",
            "x-dead-letter-routing-key": "dead",
        },
    ),
)
DEAD_LETTER_QUEUE = Queue(
    "govintel.dead",
    Exchange("govintel.dead", type="direct", durable=True),
    routing_key="dead",
    durable=True,
)
