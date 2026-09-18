from rest_framework import serializers


class SemanticSearchRequestSerializer(serializers.Serializer):
    query = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        error_messages={
            "required": "O parâmetro query é obrigatório.",
            "blank": "O parâmetro query não pode ser vazio.",
        },
    )
    tenderId = serializers.UUIDField(
        required=False,
        default=None,
        allow_null=True,
    )
    topK = serializers.IntegerField(
        required=False,
        default=8,
        min_value=1,
        max_value=50,
        error_messages={
            "min_value": "topK deve ser no mínimo 1.",
            "max_value": "topK deve ser no máximo 50.",
        },
    )
    page = serializers.IntegerField(
        required=False,
        default=1,
        min_value=1,
        error_messages={
            "min_value": "page deve ser no mínimo 1.",
        },
    )
    pageSize = serializers.IntegerField(
        required=False,
        default=20,
        min_value=1,
        max_value=50,
        error_messages={
            "min_value": "pageSize deve ser no mínimo 1.",
            "max_value": "pageSize deve ser no máximo 50.",
        },
    )
