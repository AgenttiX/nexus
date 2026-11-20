"""Restaurants and their daily menus.

Menus are public and the same for every user, so only the list of favourite
restaurants is user-owned.
"""

from typing import ClassVar

from django.db import models

from apps.core.models import OwnedManager, OwnedModel


class Restaurant(models.Model):
    """A UniCafe restaurant."""

    external_id = models.PositiveIntegerField(unique=True, help_text="The restaurant's id at UniCafe.")
    name = models.CharField(max_length=100)
    campus = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=200, blank=True)
    lunch_hours = models.CharField(max_length=200, blank=True)
    url = models.URLField(blank=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        """Return the restaurant's name."""
        return self.name


class Dish(models.Model):
    """One dish served by a restaurant on one day."""

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="dishes")
    date = models.DateField()
    position = models.PositiveSmallIntegerField(help_text="Order on the day's menu.")
    name = models.CharField(max_length=300)
    category = models.CharField(max_length=100, blank=True, help_text="For example the lunch type.")
    diets = models.JSONField(default=list, blank=True, help_text="Diet codes such as G or Veg.")
    allergens = models.JSONField(default=list, blank=True)
    prices = models.JSONField(default=dict, blank=True, help_text="Price in euros per customer group.")

    class Meta:
        ordering = ("date", "restaurant__name", "position")
        indexes = (models.Index(fields=("date", "restaurant")),)
        verbose_name_plural = "dishes"

    def __str__(self) -> str:
        """Return the dish's name."""
        return self.name


class FavouriteRestaurant(OwnedModel):
    """A restaurant whose menu a user wants to see first."""

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="+")

    objects: ClassVar[OwnedManager[FavouriteRestaurant]] = OwnedManager()

    class Meta(OwnedModel.Meta):
        constraints = (
            models.UniqueConstraint(fields=("user", "restaurant"), name="unique_favourite_restaurant"),
        )

    def __str__(self) -> str:
        """Return the restaurant's name."""
        return str(self.restaurant)
