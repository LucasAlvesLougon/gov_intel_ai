from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.conversations.models import Conversation
from apps.conversations.rag_service import process_rag_chat
from apps.conversations.serializers import (
    ChatRequestSerializer,
    MessagePublicSerializer,
)
from apps.core.exceptions import ConflictError
from apps.core.permissions import IsTenantMember, get_user_company
from apps.core.throttling import ChatThrottle
from apps.tenders.models import Tender


class TenderChatView(APIView):
    """
    Endpoint POST /api/tenders/{id}/chat/
    Processa perguntas de RAG sobre um edital com citações verificáveis.
    - Tenant derivado estritamente de request.user.
    - Edital deve pertencer à empresa e possuir status PROCESSED (senão 409).
    - Suporta criar nova conversa ou continuar conversa existente.
    """

    permission_classes = [IsAuthenticated, IsTenantMember]
    throttle_classes = [ChatThrottle]

    def post(self, request, id, *args, **kwargs):
        company = get_user_company(request.user)

        # 1. Validar edital do tenant
        tender = Tender.objects.filter(id=id, company=company).first()
        if not tender:
            raise NotFound("Edital não encontrado para este tenant.")

        if tender.status != "PROCESSED":
            raise ConflictError("O edital ainda não foi processado.")

        # 2. Validar payload da mensagem
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.validated_data["message"]
        conv_id = serializer.validated_data.get("conversationId")

        # 3. Obter ou criar conversa
        if conv_id:
            conversation = Conversation.objects.filter(
                id=conv_id,
                company=company,
                user=request.user,
                tender=tender,
            ).first()
            if not conversation:
                raise NotFound("Conversa não encontrada para este edital.")
        else:
            title = message[:50].strip() or "Nova conversa"
            conversation = Conversation.objects.create(
                company=company,
                user=request.user,
                tender=tender,
                title=title,
            )

        # 4. Executar pipeline RAG
        result = process_rag_chat(
            company=company,
            tender=tender,
            conversation=conversation,
            user_message=message,
        )

        return Response(
            {
                "conversationId": str(conversation.id),
                "message": MessagePublicSerializer(result["message"]).data,
            },
            status=status.HTTP_200_OK,
        )
