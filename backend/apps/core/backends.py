from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class CaseInsensitiveModelBackend(ModelBackend):
    """
    Autentica por email de forma insensível a maiúsculas/minúsculas,
    com tempo constante (set_password no dummy) para mitigar timing attacks.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        user_model = get_user_model()
        if username is None:
            username = kwargs.get(user_model.USERNAME_FIELD)
        if username:
            username = username.strip().lower()
        if not username or not password:
            return None
        try:
            user = user_model.objects.get(email=username)
        except user_model.DoesNotExist:
            user_model().set_password(password)
            return None
        else:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None
