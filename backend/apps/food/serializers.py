"""Serializers for restaurant menus."""

from rest_framework import serializers

from apps.food.models import Dish, Restaurant


class RestaurantSerializer(serializers.ModelSerializer[Restaurant]):
    """A restaurant, with whether it is a favourite of the signed-in user."""

    is_favourite = serializers.BooleanField(read_only=True)

    class Meta:
        model = Restaurant
        fields = ("id", "name", "campus", "address", "lunch_hours", "url", "is_favourite")


class DishSerializer(serializers.ModelSerializer[Dish]):
    """A dish on a restaurant's menu."""

    diets = serializers.ListField(child=serializers.CharField())
    allergens = serializers.ListField(child=serializers.CharField())
    prices = serializers.DictField(child=serializers.CharField())

    class Meta:
        model = Dish
        fields = ("id", "restaurant", "date", "name", "category", "diets", "allergens", "prices")
