import uuid
from datetime import UTC, datetime

from django.conf import settings
from django.db import transaction
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import RefreshTokenRecord


def get_tokens_for_user(user, family_id=None):
    """
    Gera access token (15m) e refresh token (7d) com claims necessárias.
    """
    refresh = RefreshToken.for_user(user)
    # A UUID family keeps concurrent sessions independent while allowing reuse
    # detection to revoke the complete compromised chain.
    family_id = str(family_id or uuid.uuid4())
    refresh["company_id"] = str(user.company_id)
    refresh["email"] = user.email
    refresh["role"] = user.role
    refresh["family_id"] = family_id
    RefreshTokenRecord.objects.create(
        user=user,
        family_id=family_id,
        jti=str(refresh["jti"]),
        expires_at=datetime.fromtimestamp(refresh["exp"], tz=UTC),
    )
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


def is_local_request(request):
    if request is None:
        return True
    host = request.get_host().split(":")[0]
    return host in ("localhost", "127.0.0.1", "testserver")


def set_refresh_cookie(response, refresh_token, request=None):
    """
    Define refresh token em cookie protegido httpOnly, sameSite=Lax, secure fora de localhost.
    """
    secure = not (settings.DEBUG or is_local_request(request))
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="Lax",
        secure=secure,
        max_age=7 * 24 * 60 * 60,
        path="/api/auth/",
    )


def clear_refresh_cookie(response):
    response.delete_cookie(
        key="refresh_token",
        path="/api/auth/",
    )


def decode_refresh_token(token: str) -> dict:
    """Valida assinatura/expiração sem consultar a blacklist do SimpleJWT."""
    payload = RefreshToken().get_token_backend().decode(token, verify=True)
    if payload.get("token_type") != "refresh":
        raise ValueError("Tipo de token inválido.")
    return payload


def rotate_refresh_token(token: str, user):
    """Reivindica um refresh token e emite o próximo elo da mesma família."""
    payload = decode_refresh_token(token)
    jti = str(payload["jti"])
    family_id = payload.get("family_id")
    if not family_id:
        raise ValueError("Refresh token sem família.")
    try:
        family_uuid = uuid.UUID(str(family_id))
    except ValueError as exc:
        raise ValueError("Família de refresh inválida.") from exc

    failure: str | None = None
    with transaction.atomic():
        record = (
            RefreshTokenRecord.objects.select_for_update()
            .filter(jti=jti, user=user, family_id=family_uuid)
            .first()
        )
        now = datetime.now(UTC)
        if record is None:
            failure = "Refresh token desconhecido."
        elif record.revoked_at is not None or record.replaced_by_jti or record.is_expired(now):
            RefreshTokenRecord.objects.filter(
                family_id=record.family_id,
                revoked_at__isnull=True,
            ).update(revoked_at=now)
            failure = "Refresh token reutilizado ou expirado."
        else:
            try:
                # Keep SimpleJWT's blacklist in sync with the server-side record.
                refresh = RefreshToken(token)
                refresh.blacklist()
            except Exception:
                RefreshTokenRecord.objects.filter(
                    family_id=record.family_id,
                    revoked_at__isnull=True,
                ).update(revoked_at=now)
                failure = "Refresh token inválido ou inconsistente."
            else:
                tokens = get_tokens_for_user(user, family_id=record.family_id)
                replacement = RefreshToken(tokens["refresh"])
                record.revoked_at = now
                record.replaced_by_jti = str(replacement["jti"])
                record.save(update_fields=["revoked_at", "replaced_by_jti", "updated_at"])
                return tokens

    raise ValueError(failure or "Refresh token inválido.")
