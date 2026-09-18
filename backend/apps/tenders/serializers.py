from rest_framework import serializers

from apps.pipeline.exceptions import safe_pipeline_error_message
from apps.tenders.models import Tender


class TenderPublicSerializer(serializers.ModelSerializer):
    originalFilename = serializers.CharField(source="original_filename", read_only=True)
    fileSize = serializers.IntegerField(source="file_size", read_only=True)
    pipelineGeneration = serializers.IntegerField(source="pipeline_generation", read_only=True)
    errorCode = serializers.CharField(source="error_code", read_only=True)
    errorMessage = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = Tender
        fields = (
            "id",
            "title",
            "description",
            "status",
            "originalFilename",
            "fileSize",
            "pipelineGeneration",
            "errorCode",
            "errorMessage",
            "createdAt",
            "updatedAt",
        )

    def get_errorMessage(self, obj):
        if not obj.error_code:
            return None
        return safe_pipeline_error_message(obj.error_code)


class TenderProcessingStatusSerializer(serializers.ModelSerializer):
    tenderId = serializers.UUIDField(source="id", read_only=True)
    status = serializers.CharField(read_only=True)
    progress = serializers.IntegerField(read_only=True)
    processedChunks = serializers.IntegerField(source="processed_chunks", read_only=True)
    error = serializers.SerializerMethodField()

    class Meta:
        model = Tender
        fields = (
            "tenderId",
            "status",
            "progress",
            "processedChunks",
            "error",
        )

    def get_error(self, obj):
        if obj.error_code:
            return {
                "code": obj.error_code,
                "message": safe_pipeline_error_message(obj.error_code),
            }
        return None
