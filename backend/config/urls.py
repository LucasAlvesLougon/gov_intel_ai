from django.urls import include, path

from .health import health

urlpatterns = [
    path("health/", health),
    path("api/auth/", include("apps.core.urls")),
    path("api/tenders/", include("apps.tenders.urls")),
    path("api/search/", include("apps.intelligence.urls")),
]

handler404 = "apps.core.exceptions.custom_handler404"
handler500 = "apps.core.exceptions.custom_handler500"
