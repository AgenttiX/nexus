"""Importing and reading restaurant menus."""

import datetime as dt

from django.db import transaction
from django.db.models import Exists, OuterRef, QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.food.models import Dish, FavouriteRestaurant, Restaurant
from apps.food.unicafe import FeedRestaurant, parse_date

DIET_KEY, ALLERGEN_KEY = "0", "1"


@transaction.atomic
def import_feed(feed: list[FeedRestaurant], today: dt.date | None = None) -> int:
    """Store the restaurants and menus of a feed, and return the number of dishes stored.

    Each day in the feed replaces what was stored for that restaurant and day.
    Days that the feed no longer mentions are kept as history.
    """
    today = today or timezone.localdate()
    stored = 0
    for item in feed:
        restaurant, _ = Restaurant.objects.update_or_create(
            external_id=item.id,
            defaults={
                "name": item.title,
                "campus": item.campus,
                "address": item.address,
                "lunch_hours": item.lunch_hours,
                "url": item.permalink,
            },
        )
        for day in item.menuData.menus:
            date = parse_date(day.date, today)
            if date is None:
                continue
            Dish.objects.filter(restaurant=restaurant, date=date).delete()
            dishes = [
                Dish(
                    restaurant=restaurant,
                    date=date,
                    position=position,
                    name=dish.name,
                    category=dish.price.name,
                    diets=dish.meta.get(DIET_KEY, []),
                    allergens=dish.meta.get(ALLERGEN_KEY, []),
                    prices=dish.price.value,
                )
                for position, dish in enumerate(day.data)
            ]
            Dish.objects.bulk_create(dishes)
            stored += len(dishes)
    return stored


def restaurants_for(user: User) -> QuerySet[Restaurant]:
    """Return all restaurants, each marked with whether it is a favourite of ``user``."""
    favourite = FavouriteRestaurant.objects.for_user(user).filter(restaurant=OuterRef("pk"))
    return Restaurant.objects.annotate(is_favourite=Exists(favourite))


def set_favourite(user: User, restaurant: Restaurant, *, favourite: bool) -> None:
    """Add ``restaurant`` to the favourites of ``user``, or remove it."""
    if favourite:
        FavouriteRestaurant.objects.get_or_create(user=user, restaurant=restaurant)
    else:
        FavouriteRestaurant.objects.for_user(user).filter(restaurant=restaurant).delete()


def menu_text(user: User, date: dt.date, restaurant: str = "") -> str:
    """Return the menus of one day as compact text for an AI agent.

    With ``restaurant``, the restaurants whose name contains it are shown.
    Otherwise the user's favourites are shown, and without favourites only the
    names of the restaurants, so that the answer stays short.
    """
    restaurants = restaurants_for(user)
    if restaurant:
        restaurants = restaurants.filter(name__icontains=restaurant)
        if not restaurants:
            return f"No restaurant matches {restaurant!r}. Restaurants: {_names(Restaurant.objects.all())}"
    else:
        restaurants = restaurants.filter(is_favourite=True)
        if not restaurants:
            return f"No favourite restaurants. Name one of: {_names(Restaurant.objects.all())}"

    blocks: list[str] = []
    for item in restaurants:
        header = f"{item.name} ({item.campus}), lunch {item.lunch_hours or 'hours unknown'}"
        dishes = [_dish_line(dish) for dish in item.dishes.filter(date=date)]
        blocks.append("\n".join([header, *(dishes or ["- no menu"])]))
    return f"{date:%a %Y-%m-%d}\n" + "\n\n".join(blocks)


def _names(restaurants: QuerySet[Restaurant]) -> str:
    return ", ".join(restaurants.values_list("name", flat=True)) or "(none loaded yet)"


def _dish_line(dish: Dish) -> str:
    details = ", ".join(part for part in (dish.category, " ".join(dish.diets)) if part)
    price = dish.prices.get("student")
    return f"- {dish.name}" + (f" [{details}]" if details else "") + (f" {price} €" if price else "")
