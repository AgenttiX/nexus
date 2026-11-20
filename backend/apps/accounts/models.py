"""User model."""

from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """A person using this Nexus deployment.

    A custom model from the first migration, so that fields can be added later
    without the pain of swapping the user model.
    """
