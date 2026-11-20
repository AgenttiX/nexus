"""URLs of the sleep app."""

from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.sleep.api import SleepRecordViewSet, SleepSummaryView

router = SimpleRouter()
router.register("sleep/records", SleepRecordViewSet, basename="sleep-record")

urlpatterns = [
    path("sleep/summary/", SleepSummaryView.as_view(), name="sleep-summary"),
    *router.urls,
]
