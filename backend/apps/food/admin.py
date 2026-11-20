"""Admin registrations for restaurant menus."""

from django.contrib import admin

from apps.food.models import Dish, Restaurant


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    """Restaurants, as imported from the feed."""

    list_display = ("name", "campus", "lunch_hours")
    search_fields = ("name",)


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    """Dishes, as imported from the feed."""

    list_display = ("name", "restaurant", "date", "category")
    list_filter = ("restaurant", "date")
