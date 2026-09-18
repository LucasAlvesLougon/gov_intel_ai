from django.contrib.auth import authenticate
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.jwt_utils import (
    clear_refresh_cookie,
    decode_refresh_token,
    get_tokens_for_user,
    rotate_refresh_token,
    set_refresh_cookie,
)
from apps.core.models import RefreshTokenRecord, User
from apps.core.serializers import (
    CompanyPublicSerializer,
    LoginInputSerializer,
    RegisterInputSerializer,
    UserPublicSerializer,
)
from apps.core.services import register_company_and_owner
from apps.core.throttling import LoginThrottle, RefreshThrottle, RegisterThrottle


class CsrfView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [RegisterThrottle]

    def post(self, request):
        serializer = RegisterInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, company = register_company_and_owner(
            company_name=serializer.validated_data["companyName"],
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        tokens = get_tokens_for_user(user)
        response_data = {
            "user": UserPublicSerializer(user).data,
            "company": CompanyPublicSerializer(company).data,
            "accessToken": tokens["access"],
        }
        response = Response(response_data, status=status.HTTP_201_CREATED)
        set_refresh_cookie(response, tokens["refresh"], request=request)
        return response


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request):
        serializer = LoginInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        user = authenticate(request, username=email, password=password)
        if not user or not user.is_active:
            raise AuthenticationFailed("Credenciais inválidas.")

        tokens = get_tokens_for_user(user)
        response_data = {
            "accessToken": tokens["access"],
            "user": UserPublicSerializer(user).data,
            "company": CompanyPublicSerializer(user.company).data,
        }
        response = Response(response_data, status=status.HTTP_200_OK)
        set_refresh_cookie(response, tokens["refresh"], request=request)
        return response


class TokenRefreshView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [RefreshThrottle]

    def post(self, request):
        token = request.COOKIES.get("refresh_token")
        if not token:
            raise AuthenticationFailed("Token de atualização ausente.")

        try:
            payload = decode_refresh_token(token)
            user_id = payload.get("user_id")
            user = User.objects.get(id=user_id, is_active=True)
            tokens = rotate_refresh_token(token, user)
            response = Response({"accessToken": tokens["access"]}, status=status.HTTP_200_OK)
            set_refresh_cookie(response, tokens["refresh"], request=request)
            return response
        except Exception as exc:
            raise AuthenticationFailed("Token de atualização inválido ou expirado.") from exc


class LogoutView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [RefreshThrottle]

    def post(self, request):
        token = request.COOKIES.get("refresh_token")
        if token:
            try:
                refresh = RefreshToken(token)
                with transaction.atomic():
                    record = (
                        RefreshTokenRecord.objects.select_for_update()
                        .filter(jti=str(refresh["jti"]))
                        .first()
                    )
                    refresh.blacklist()
                    if record:
                        RefreshTokenRecord.objects.filter(
                            family_id=record.family_id,
                            revoked_at__isnull=True,
                        ).update(revoked_at=timezone.now())
            except Exception:
                pass
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_refresh_cookie(response)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "user": UserPublicSerializer(request.user).data,
                "company": CompanyPublicSerializer(request.user.company).data,
            },
            status=status.HTTP_200_OK,
        )
