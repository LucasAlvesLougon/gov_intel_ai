import hashlib
import uuid
from typing import Any

from django.conf import settings
from django.core.cache import cache

DEFAULT_SEARCH_CACHE_TTL = 300  # 5 minutos segundo docs/api-contract.md


def get_company_data_revision(company_id: str | uuid.UUID) -> int:
    """
    Retorna a revisão atual de dados da empresa para invalidação rápida sem SCAN.
    Chave no Redis: govintel:v1:revision:{companyId}
    """
    rev_key = f"govintel:v1:revision:{company_id}"
    rev = cache.get(rev_key)
    if rev is None:
        cache.set(rev_key, 1, timeout=None)
        return 1
    return int(rev)


def increment_company_data_revision(company_id: str | uuid.UUID) -> int:
    """
    Incrementa a revisão de dados da empresa, invalidando instantaneamente
    todo o cache de busca semântica deste tenant.
    """
    rev_key = f"govintel:v1:revision:{company_id}"
    try:
        new_val = cache.incr(rev_key)
        return int(new_val)
    except Exception:
        curr = cache.get(rev_key)
        new_val = (int(curr) + 1) if curr is not None else 2
        cache.set(rev_key, new_val, timeout=None)
        return new_val


def generate_semantic_search_cache_key(
    company_id: str | uuid.UUID,
    query: str,
    tender_id: str | uuid.UUID | None = None,
    top_k: int = 8,
    page: int = 1,
    page_size: int = 20,
    scope: str = "company",
    embedding_version: str = "v1",
    index_version: str = "v1",
) -> str:
    """
    Gera chave de cache canônica segundo o contrato em docs/api-contract.md:
    govintel:v1:semantic:{companyId}:{scope}:{dataRevision}:{embeddingVersion}:{indexVersion}:{sha256(canonicalQuery+filters)}
    """
    data_rev = get_company_data_revision(company_id)
    canonical_filters = (
        f"tenderId={tender_id or ''}&topK={top_k}&page={page}&pageSize={page_size}"
    )
    canonical_payload = f"query={query.strip().lower()}&{canonical_filters}"
    payload_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

    return (
        f"govintel:v1:semantic:{company_id}:{scope}:{data_rev}:"
        f"{embedding_version}:{index_version}:{payload_hash}"
    )


def get_search_cache(key: str) -> dict[str, Any] | None:
    return cache.get(key)


def set_search_cache(
    key: str, data: dict[str, Any], timeout: int | None = None
) -> None:
    ttl = (
        timeout
        if timeout is not None
        else getattr(settings, "SEARCH_CACHE_TTL", DEFAULT_SEARCH_CACHE_TTL)
    )
    cache.set(key, data, timeout=ttl)
