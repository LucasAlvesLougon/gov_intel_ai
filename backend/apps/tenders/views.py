import hashlib
import math
import uuid

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import UnprocessableEntityError
from apps.core.permissions import filter_by_tenant, get_user_company
from apps.core.throttling import UploadThrottle
from apps.intelligence.cache import increment_company_data_revision
from apps.pipeline.outbox import process_outbox_batch, schedule_tender_processing
from apps.tenders.models import IdempotencyKey, Tender
from apps.tenders.serializers import TenderProcessingStatusSerializer, TenderPublicSerializer
from apps.tenders.storage import get_storage_adapter
from apps.tenders.validators import validate_pdf_upload


class TenderListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_throttles(self):
        if self.request.method == "POST":
            return [UploadThrottle()]
        return []

    def get(self, request):
        queryset = filter_by_tenant(Tender.objects.all(), request.user)

        # Filtro opcional por status
        tender_status = request.query_params.get("status")
        if tender_status:
            queryset = queryset.filter(status=tender_status)

        # Ordenação
        sort_by = request.query_params.get("sortBy", "createdAt")
        sort_order = request.query_params.get("sortOrder", "desc")
        field_map = {
            "createdAt": "created_at",
            "updatedAt": "updated_at",
            "title": "title",
            "status": "status",
        }
        order_field = field_map.get(sort_by, "created_at")
        if sort_order.lower() == "desc":
            order_field = f"-{order_field}"
        queryset = queryset.order_by(order_field)

        # Paginação
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except (ValueError, TypeError):
            page = 1

        try:
            page_size = min(50, max(1, int(request.query_params.get("pageSize", 20))))
        except (ValueError, TypeError):
            page_size = 20

        total_items = queryset.count()
        total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0

        offset = (page - 1) * page_size
        items = queryset[offset : offset + page_size]

        serializer = TenderPublicSerializer(items, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {
                    "page": page,
                    "pageSize": page_size,
                    "totalItems": total_items,
                    "totalPages": total_pages,
                },
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        company = get_user_company(request.user)
        uploaded_file = request.FILES.get("file")

        file_bytes, sha256_hash = validate_pdf_upload(uploaded_file)

        title = request.data.get("title") or uploaded_file.name
        description = request.data.get("description", "")
        canonical_hash = hashlib.sha256(
            f"{sha256_hash}:{title.strip()}:{description.strip()}".encode()
        ).hexdigest()

        idempotency_key = (
            request.headers.get("Idempotency-Key") or request.META.get("HTTP_IDEMPOTENCY_KEY")
        )

        if idempotency_key:
            with transaction.atomic():
                existing = (
                    IdempotencyKey.objects.select_for_update()
                    .filter(
                        company=company,
                        user=request.user,
                        endpoint="/api/tenders/",
                        key=idempotency_key,
                    )
                    .first()
                )
                if existing:
                    if existing.request_hash != canonical_hash:
                        raise UnprocessableEntityError(
                            "Chave de idempotência já utilizada com um payload diferente."
                        )
                    if existing.tender:
                        serializer = TenderPublicSerializer(existing.tender)
                        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
                    if existing.response_data:
                        return Response(existing.response_data, status=existing.status_code)
                    return Response(status=status.HTTP_202_ACCEPTED)

                tender_id = uuid.uuid4()
                storage = get_storage_adapter()
                storage_key = storage.save(company.id, tender_id, file_bytes)

                tender = Tender.objects.create(
                    id=tender_id,
                    company=company,
                    title=title,
                    description=description,
                    status="PENDING",
                    original_filename=uploaded_file.name,
                    storage_key=storage_key,
                    file_size=len(file_bytes),
                    sha256=sha256_hash,
                )
                schedule_tender_processing(tender)
                serializer = TenderPublicSerializer(tender)
                IdempotencyKey.objects.create(
                    company=company,
                    user=request.user,
                    endpoint="/api/tenders/",
                    key=idempotency_key,
                    request_hash=canonical_hash,
                    tender=tender,
                    status_code=status.HTTP_202_ACCEPTED,
                    response_data=serializer.data,
                )

            # Publica somente após o commit para evitar que o worker consuma a
            # mensagem antes de o edital estar visível no banco.
            transaction.on_commit(process_outbox_batch)
            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)

        # Sem chave de idempotência
        with transaction.atomic():
            tender_id = uuid.uuid4()
            storage = get_storage_adapter()
            storage_key = storage.save(company.id, tender_id, file_bytes)

            tender = Tender.objects.create(
                id=tender_id,
                company=company,
                title=title,
                description=description,
                status="PENDING",
                original_filename=uploaded_file.name,
                storage_key=storage_key,
                file_size=len(file_bytes),
                sha256=sha256_hash,
            )
            schedule_tender_processing(tender)

        process_outbox_batch()
        serializer = TenderPublicSerializer(tender)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)


class TenderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        queryset = filter_by_tenant(Tender.objects.all(), request.user)
        tender = get_object_or_404(queryset, id=id)
        serializer = TenderPublicSerializer(tender)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, id):
        queryset = filter_by_tenant(Tender.objects.all(), request.user)
        tender = get_object_or_404(queryset, id=id)

        # Cleanup de blob no storage privado
        if tender.storage_key:
            storage = get_storage_adapter()
            storage.delete(tender.storage_key)

        company_id = tender.company_id
        tender.delete()
        increment_company_data_revision(company_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TenderProcessingStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        queryset = filter_by_tenant(Tender.objects.all(), request.user)
        tender = get_object_or_404(queryset, id=id)
        serializer = TenderProcessingStatusSerializer(tender)
        response = Response(serializer.data, status=status.HTTP_200_OK)
        if tender.status in ["PENDING", "PROCESSING"]:
            response["Retry-After"] = "2"
        return response
