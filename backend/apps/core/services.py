from django.db import IntegrityError, transaction

from apps.core.exceptions import ConflictError
from apps.core.models import Company, User


@transaction.atomic
def register_company_and_owner(
    company_name: str,
    email: str,
    password: str,
) -> tuple[User, Company]:
    """
    Cria empresa e usuário proprietário de forma estritamente atômica.
    Email duplicado levanta ConflictError (HTTP 409).
    Falha na criação do usuário reverte a empresa criada.
    """
    normalized_email = email.strip().lower()
    if User.objects.filter(email=normalized_email).exists():
        raise ConflictError("Email já cadastrado.")

    company = Company.objects.create(name=company_name)
    try:
        user = User.objects.create_user(
            email=normalized_email,
            password=password,
            company=company,
            role="OWNER",
        )
    except IntegrityError as exc:
        raise ConflictError("Email já cadastrado.") from exc

    return user, company
