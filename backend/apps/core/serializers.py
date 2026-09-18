from rest_framework import serializers

from apps.core.models import Company, User


class RegisterInputSerializer(serializers.Serializer):
    companyName = serializers.CharField(max_length=255, required=True, allow_blank=False)
    email = serializers.EmailField(max_length=255, required=True)
    password = serializers.CharField(max_length=128, required=True, min_length=8, write_only=True)


class LoginInputSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)


class CompanyPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ("id", "name", "slug")


class UserPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "role")
