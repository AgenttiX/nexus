"""API views for accounts."""

from django.db.models import QuerySet
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.generics import RetrieveAPIView
from rest_framework.serializers import BaseSerializer

from apps.accounts.models import AgentToken, User
from apps.accounts.serializers import AgentTokenSerializer, CreatedAgentTokenSerializer, CurrentUserSerializer


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CurrentUserView(RetrieveAPIView[User]):
    """Return the signed-in user. The frontend uses a 403 here to start the login redirect.

    The response also sets the CSRF cookie, which the frontend needs before it
    can send any request that changes data.
    """

    serializer_class = CurrentUserSerializer

    def get_object(self) -> User:
        """Return the user of the current session."""
        user = self.request.user
        assert isinstance(user, User)  # noqa: S101 - guaranteed by IsAuthenticated
        return user


@extend_schema_view(create=extend_schema(responses={201: CreatedAgentTokenSerializer}))
class AgentTokenViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet[AgentToken],
):
    """The signed-in user's agent tokens.

    Tokens cannot be edited: to change an agent's access, delete its token and
    create a new one, so that a scope change is never silent.
    """

    queryset = AgentToken.objects.none()

    def get_queryset(self) -> QuerySet[AgentToken]:
        """Return only the tokens of the signed-in user."""
        user = self.request.user
        assert isinstance(user, User)  # noqa: S101 - guaranteed by IsAuthenticated
        return AgentToken.objects.for_user(user)

    def get_serializer_class(self) -> type[BaseSerializer[AgentToken]]:
        """Include the secret only in the response to creation."""
        return CreatedAgentTokenSerializer if self.action == "create" else AgentTokenSerializer

    def perform_create(self, serializer: BaseSerializer[AgentToken]) -> None:
        """Create the token for the signed-in user."""
        serializer.save(user=self.request.user)
