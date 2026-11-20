"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView

from apps.core.views import spa

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/", include("apps.core.urls")),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.food.urls")),
    path("api/", include("apps.calendars.urls")),
    path("api/", include("apps.sleep.urls")),
    # Everything else belongs to the single-page application.
    re_path(r"^(?!api/|admin/|accounts/|static/|assets/).*$", spa, name="spa"),
]
