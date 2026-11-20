"""URLs of the food app."""

from rest_framework.routers import SimpleRouter

from apps.food.api import DishViewSet, RestaurantViewSet

router = SimpleRouter()
router.register("food/restaurants", RestaurantViewSet, basename="restaurant")
router.register("food/dishes", DishViewSet, basename="dish")

urlpatterns = router.urls
