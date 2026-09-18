from rest_framework import serializers

from apps.conversations.models import Conversation, Message


class MessagePublicSerializer(serializers.ModelSerializer):
    conversationId = serializers.UUIDField(source="conversation_id", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = Message
        fields = (
            "id",
            "conversationId",
            "role",
            "content",
            "citations",
            "createdAt",
        )
        read_only_fields = fields


class ConversationPublicSerializer(serializers.ModelSerializer):
    tenderId = serializers.UUIDField(source="tender_id", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    messages = MessagePublicSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = (
            "id",
            "tenderId",
            "title",
            "createdAt",
            "updatedAt",
            "messages",
        )
        read_only_fields = fields


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        error_messages={
            "required": "O parâmetro message é obrigatório.",
            "blank": "O parâmetro message não pode ser vazio.",
        },
    )
    conversationId = serializers.UUIDField(
        required=False,
        allow_null=True,
        default=None,
    )

