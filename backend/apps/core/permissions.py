from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from apps.core.models import Company


def get_user_company(user) -> Company:
    """
    Deriva a empresa de forma estrita a partir de request.user.
    Nunca aceita companyId originado de payload ou parâmetros do cliente.
    """
    if not user or not user.is_authenticated or not hasattr(user, "company"):
        raise PermissionDenied("Usuário não possui uma empresa associada.")
    return user.company


def filter_by_tenant(queryset, user):
    """
    Garante que qualquer queryset dependente de tenant seja filtrado
    estritamente pela empresa do usuário autenticado.
    """
    company = get_user_company(user)
    return queryset.filter(company_id=company.id)


class IsTenantMember(BasePermission):
    """
    Permissão DRF que valida se o recurso pertence ao mesmo tenant do usuário autenticado.
    Se o objeto possuir company_id, ele deve ser idêntico ao request.user.company_id.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.company_id)

    def has_object_permission(self, request, view, obj):
        if not (request.user and request.user.is_authenticated):
            return False
        obj_company_id = getattr(obj, "company_id", None)
        if obj_company_id is None and hasattr(obj, "company"):
            obj_company_id = getattr(obj.company, "id", None)
        return obj_company_id == request.user.company_id
