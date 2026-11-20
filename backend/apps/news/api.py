"""REST API for news."""

from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.news import services, tasks
from apps.news.models import Digest, NewsProfile
from apps.news.serializers import DigestSerializer, NewsProfileSerializer, SourceSerializer
from apps.news.sources import SOURCES


def _user(request: Request) -> User:
    user = request.user
    assert isinstance(user, User)  # noqa: S101 - guaranteed by IsAuthenticated
    return user


class NewsProfileView(RetrieveUpdateAPIView[NewsProfile]):
    """The signed-in user's news settings."""

    serializer_class = NewsProfileSerializer

    def get_object(self) -> NewsProfile:
        """Return the user's settings, created with defaults on first use."""
        return services.profile_for(_user(self.request))


class SourceListView(APIView):
    """The news sites that Nexus can read."""

    @extend_schema(responses=SourceSerializer(many=True))
    def get(self, request: Request) -> Response:
        """Return all sources. ``full_text`` tells whether article texts are read, or only leads."""
        return Response(SourceSerializer(SOURCES.values(), many=True).data)


class DigestViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet[Digest]):
    """The signed-in user's news digests, newest first."""

    serializer_class = DigestSerializer
    queryset = Digest.objects.none()

    def get_queryset(self) -> QuerySet[Digest]:
        """Return only the digests of the signed-in user."""
        return Digest.objects.for_user(_user(self.request)).prefetch_related("selected__article")

    @extend_schema(request=None, responses={202: DigestSerializer})
    @action(detail=False, methods=["post"])
    def generate(self, request: Request) -> Response:
        """Read the feeds and write today's digest in the background, replacing an earlier one."""
        digest = services.start_digest(_user(request))
        tasks.write_digest.delay(digest.pk, fetch_first=True)
        return Response(DigestSerializer(digest).data, status=status.HTTP_202_ACCEPTED)
