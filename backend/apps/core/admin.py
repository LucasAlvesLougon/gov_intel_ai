from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Company, User


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")
    readonly_fields = ("id", "slug", "created_at", "updated_at")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "company", "role", "is_active", "is_staff")
    search_fields = ("email", "company__name")
    ordering = ("email",)
    readonly_fields = ("id", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Tenant & Permissões",
            {"fields": ("company", "role", "is_active", "is_staff", "is_superuser")},
        ),
        ("Datas", {"fields": ("created_at", "updated_at")}),
    )
