"""API views for accounts."""

from rest_framework.generics import RetrieveAPIView

from apps.accounts.models import User
from apps.accounts.serializers import CurrentUserSerializer


class CurrentUserView(RetrieveAPIView[User]):
    """Return the signed-in user. The frontend uses a 403 here to start the login redirect."""

    serializer_class = CurrentUserSerializer

    def get_object(self) -> User:
        """Return the user of the current session."""
        user = self.request.user
        assert isinstance(user, User)  # noqa: S101 - guaranteed by IsAuthenticated
        return user
