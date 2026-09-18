from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsTenantMember, get_user_company
from apps.core.throttling import SearchThrottle
from apps.intelligence.cache import (
    generate_semantic_search_cache_key,
    get_search_cache,
    set_search_cache,
)
from apps.intelligence.embeddings import get_embedding_adapter, get_embedding_metadata
from apps.intelligence.repository import VectorSearchRepository
from apps.intelligence.serializers import SemanticSearchRequestSerializer
from apps.tenders.models import Tender


class SemanticSearchView(APIView):
    """
    Endpoint POST /api/search/semantic/
    Executa busca semântica por similaridade de cosseno nos editais processados do tenant.
    - Autenticação Bearer obrigatória.
    - Isolamento rigoroso por empresa derivada de request.user.
    - Filtro opcional por edital (tenderId pertencente ao tenant).
    - Suporte a topK (máx 50) e paginação com page e pageSize (máx 50).
    - Cache Redis com chave canônica versionada e particionada por tenant.
    """

    permission_classes = [IsAuthenticated, IsTenantMember]
    throttle_classes = [SearchThrottle]

    def post(self, request, *args, **kwargs):
        serializer = SemanticSearchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        company = get_user_company(request.user)
        query = data["query"]
        tender_id = data.get("tenderId")
        top_k = data.get("topK", 8)
        page = data.get("page", 1)
        page_size = data.get("pageSize", 20)

        # Validação de tenderId se fornecido
        if tender_id:
            tender_exists = Tender.objects.filter(id=tender_id, company=company).exists()
            if not tender_exists:
                raise NotFound("Edital não encontrado para este tenant.")

        # A identidade completa evita misturar resultados de espaços vetoriais
        # diferentes quando o modelo, revisão ou pré-processamento muda.
        adapter = get_embedding_adapter()
        embedding_metadata = get_embedding_metadata(adapter)

        # Verificar cache Redis
        cache_key = generate_semantic_search_cache_key(
            company_id=company.id,
            query=query,
            tender_id=tender_id,
            top_k=top_k,
            page=page,
            page_size=page_size,
            embedding_version=embedding_metadata["preprocessing_fingerprint"],
            index_version="v5",  # v5: identidade completa do espaço vetorial
        )
        cached_response = get_search_cache(cache_key)
        if cached_response is not None:
            return Response(cached_response, status=status.HTTP_200_OK)

        # Obter embedding para a consulta
        query_vector = adapter.embed_query(query)

        # Executar busca no repositório com overfetch e fallback exato
        repo = VectorSearchRepository()
        all_results = repo.search(
            company=company,
            query_vector=query_vector,
            tender_id=tender_id,
            top_k=top_k,
            query_text=query,
        )

        total_items = len(all_results)
        total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 0

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paged_results = all_results[start_idx:end_idx]

        response_data = {
            "data": paged_results,
            "pagination": {
                "page": page,
                "pageSize": page_size,
                "totalItems": total_items,
                "totalPages": total_pages,
            },
        }

        # Armazenar no cache Redis
        set_search_cache(cache_key, response_data)

        return Response(response_data, status=status.HTTP_200_OK)
