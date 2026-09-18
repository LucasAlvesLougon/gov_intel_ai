from django.urls import path

from apps.conversations.views import TenderChatView
from apps.tenders.views import (
    TenderDetailView,
    TenderListCreateView,
    TenderProcessingStatusView,
)

urlpatterns = [
    path("", TenderListCreateView.as_view(), name="tender-list"),
    path("<uuid:id>/", TenderDetailView.as_view(), name="tender-detail"),
    path(
        "<uuid:id>/processing-status/",
        TenderProcessingStatusView.as_view(),
        name="tender-processing-status",
    ),
    path("<uuid:id>/chat/", TenderChatView.as_view(), name="tender-chat"),
]


