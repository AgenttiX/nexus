"""URLs of the accounts app."""

from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.accounts.views import AgentTokenViewSet, CurrentUserView

router = SimpleRouter()
router.register("agent-tokens", AgentTokenViewSet, basename="agent-token")

urlpatterns = [
    path("me/", CurrentUserView.as_view(), name="me"),
    *router.urls,
]
