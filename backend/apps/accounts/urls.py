"""URLs of the accounts app."""

from django.urls import path

from apps.accounts.views import CurrentUserView

urlpatterns = [
    path("me/", CurrentUserView.as_view(), name="me"),
]
