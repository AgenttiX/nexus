"""URLs of the time tracking app."""

from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.timetracking.api import BucketViewSet, TimeSummaryView

router = SimpleRouter()
router.register("timetracking/buckets", BucketViewSet, basename="bucket")

urlpatterns = [
    path("timetracking/summary/", TimeSummaryView.as_view(), name="time-summary"),
    *router.urls,
]
