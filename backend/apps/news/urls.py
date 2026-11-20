"""URLs of the news app."""

from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.news.api import DigestViewSet, NewsProfileView, SourceListView

router = SimpleRouter()
router.register("news/digests", DigestViewSet, basename="digest")

urlpatterns = [
    path("news/profile/", NewsProfileView.as_view(), name="news-profile"),
    path("news/sources/", SourceListView.as_view(), name="news-sources"),
    *router.urls,
]
