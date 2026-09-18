from django.urls import path

from apps.intelligence.views import SemanticSearchView

urlpatterns = [
    path("semantic/", SemanticSearchView.as_view(), name="semantic-search"),
]
