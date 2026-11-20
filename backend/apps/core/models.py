"""Base classes for models that belong to one user."""

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.db import models


class OwnedManager[M: "OwnedModel"](models.Manager[M]):
    """Manager of rows that each belong to one user."""

    def for_user(self, user: AbstractBaseUser) -> models.QuerySet[M]:
        """Return only the rows of ``user``. Every read on behalf of a user starts here."""
        return self.filter(user=user)


class OwnedModel(models.Model):
    """A row that belongs to one user and must never be shown to another."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")

    class Meta:
        abstract = True
