"""URLs of the calendars app."""

from rest_framework.routers import SimpleRouter

from apps.calendars.api import CalendarViewSet, EventViewSet

router = SimpleRouter()
router.register("calendars/calendars", CalendarViewSet, basename="calendar")
router.register("calendars/events", EventViewSet, basename="event")

urlpatterns = router.urls
