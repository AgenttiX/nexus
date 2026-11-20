"""Views that are not tied to any feature."""

from django.conf import settings
from django.db import connection
from django.http import FileResponse, Http404, HttpRequest
from django.views.decorators.http import require_safe
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """Liveness and database check for container health checks. Reveals nothing else."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(
        responses=inline_serializer("Health", {"status": serializers.CharField()}),
    )
    def get(self, request: Request) -> Response:
        """Return ``ok`` when the database answers."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return Response({"status": "ok"})


@require_safe
def spa(request: HttpRequest) -> FileResponse:  # noqa: ARG001
    """Serve the single-page application for client-side routes such as ``/sleep``."""
    index = settings.FRONTEND_DIR / "index.html"
    if not index.is_file():
        msg = "The frontend has not been built."
        raise Http404(msg)
    return FileResponse(index.open("rb"), content_type="text/html")
