from django.urls import path
from django.views.decorators.csrf import csrf_protect

from apps.core.views import (
    CsrfView,
    LoginView,
    LogoutView,
    MeView,
    RegisterView,
    TokenRefreshView,
)


def protected(view_class):
    """Aplica CSRF a APIView, removendo o csrf_exempt padrão do DRF."""
    view = csrf_protect(view_class.as_view())
    view.csrf_exempt = False
    return view

urlpatterns = [
    path("csrf/", CsrfView.as_view(), name="auth-csrf"),
    path("register/", protected(RegisterView), name="auth-register"),
    path("token/", protected(LoginView), name="auth-token"),
    path(
        "token/refresh/",
        protected(TokenRefreshView),
        name="auth-token-refresh",
    ),
    path("logout/", protected(LogoutView), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
]
