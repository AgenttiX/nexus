"""REST API for restaurant menus."""

from django.db.models import QuerySet
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import User
from apps.food import services
from apps.food.models import Dish, Restaurant
from apps.food.serializers import DishSerializer, RestaurantSerializer


class RestaurantViewSet(viewsets.ReadOnlyModelViewSet[Restaurant]):
    """Restaurants, and the signed-in user's favourites among them."""

    serializer_class = RestaurantSerializer
    queryset = Restaurant.objects.none()

    def get_queryset(self) -> QuerySet[Restaurant]:
        """Return all restaurants, marked with the signed-in user's favourites."""
        user = self.request.user
        assert isinstance(user, User)  # noqa: S101 - guaranteed by IsAuthenticated
        return services.restaurants_for(user)

    @extend_schema(request=None, responses={204: None}, methods=["PUT"])
    @extend_schema(responses={204: None}, methods=["DELETE"])
    @action(detail=True, methods=["put", "delete"])
    def favourite(self, request: Request, pk: str | None = None) -> Response:
        """Mark the restaurant as a favourite (PUT) or remove the mark (DELETE)."""
        user = request.user
        assert isinstance(user, User)  # noqa: S101 - guaranteed by IsAuthenticated
        services.set_favourite(user, self.get_object(), favourite=request.method == "PUT")
        return Response(status=status.HTTP_204_NO_CONTENT)


class DishFilter(filters.FilterSet):
    """Filter dishes by day and restaurant."""

    class Meta:
        model = Dish
        fields = ("date", "restaurant")


class DishViewSet(viewsets.ReadOnlyModelViewSet[Dish]):
    """Dishes on the menus. Filter by ``date`` to get one day."""

    serializer_class = DishSerializer
    queryset = Dish.objects.all()
    filterset_class = DishFilter
