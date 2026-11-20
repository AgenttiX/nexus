"""Tests for the food app."""

import datetime as dt
import json
from pathlib import Path

import httpx
import pytest
import respx
from rest_framework.test import APIClient
from starlette.testclient import TestClient

from apps.accounts.models import User
from apps.food import mcp as food_mcp
from apps.food import services
from apps.food.models import Dish, FavouriteRestaurant, Restaurant
from apps.food.tasks import fetch_menus
from apps.food.unicafe import FEED_URL, FeedRestaurant, fetch_feed, parse_date, parse_feed
from nexus import celery_app
from tests.mcp_helpers import call, text, token_for, tool_names

FIXTURE = json.loads((Path(__file__).parent / "data" / "unicafe.json").read_text())
TODAY = dt.date(2026, 11, 20)
MONDAY = dt.date(2026, 11, 16)


@pytest.fixture
def menus(db: None) -> None:
    """The menus of the fixture feed, imported."""
    services.import_feed(parse_feed(FIXTURE), today=TODAY)


@pytest.fixture
def exactum(menus: None) -> Restaurant:
    return Restaurant.objects.get(name="Exactum")


# Feed parsing


@pytest.mark.parametrize(
    ("text", "today", "expected"),
    [
        ("Mon 16.11.", dt.date(2026, 11, 20), dt.date(2026, 11, 16)),
        ("Fri 2.1.", dt.date(2026, 12, 29), dt.date(2027, 1, 2)),
        ("Wed 30.12.", dt.date(2027, 1, 2), dt.date(2026, 12, 30)),
        ("Sat 29.2.", dt.date(2027, 3, 1), dt.date(2028, 2, 29)),
        ("31.2.", dt.date(2026, 3, 1), None),
        ("tomorrow", dt.date(2026, 3, 1), None),
    ],
)
def test_feed_dates_get_the_nearest_year(text: str, today: dt.date, expected: dt.date | None) -> None:
    assert parse_date(text, today) == expected


def test_feed_parsing_keeps_valid_restaurants_and_skips_the_rest() -> None:
    feed = parse_feed([*FIXTURE, {"title": "no id"}, "nonsense"])
    assert [item.title for item in feed] == ["Olivia staff restaurant", "Exactum"]
    assert feed[1].campus == "Kumpula"
    assert feed[1].lunch_hours == "Mon–Fri 11.00-14.00, Sat–Sun Closed"


def test_feed_must_be_a_list() -> None:
    with pytest.raises(TypeError):
        parse_feed({"error": "maintenance"})


def test_lunch_hours_fall_back_to_opening_hours_or_nothing() -> None:
    hours = {"business": {"items": [{"label": "Mon–Fri", "hours": "11:00-13:30"}]}, "lounas": False}
    restaurant = FeedRestaurant.model_validate({"id": 1, "title": "A", "menuData": {"visitingHours": hours}})
    assert restaurant.lunch_hours == "Mon–Fri 11:00-13:30"
    priceless = {
        "date": "Mon 16.11.",
        "data": [{"name": "Notice", "price": {"name": "Tiedote", "value": []}}],
    }
    bare = FeedRestaurant.model_validate({"id": 2, "title": "B", "menuData": {"menus": [priceless]}})
    assert bare.menuData.menus[0].data[0].price.value == {}
    assert bare.lunch_hours == ""
    assert bare.campus == ""


@respx.mock
def test_fetch_feed_downloads_and_parses() -> None:
    route = respx.get(FEED_URL, params={"lang": "en"}).mock(return_value=httpx.Response(200, json=FIXTURE))
    assert len(fetch_feed()) == 2
    assert route.called


@respx.mock
def test_fetch_feed_fails_on_http_errors() -> None:
    respx.get(FEED_URL).mock(return_value=httpx.Response(503))
    with pytest.raises(httpx.HTTPStatusError):
        fetch_feed()


# Import


def test_import_stores_restaurants_and_dishes(exactum: Restaurant) -> None:
    assert Restaurant.objects.count() == 2
    assert (exactum.campus, exactum.lunch_hours) == ("Kumpula", "Mon–Fri 11.00-14.00, Sat–Sun Closed")
    assert str(exactum) == "Exactum"
    dishes = list(exactum.dishes.filter(date=MONDAY))
    assert len(dishes) == 3
    first = dishes[0]
    assert str(first) == first.name == "Chipotle sweet potato soup & avocado foam"
    assert first.category == "Vegaanilounas"
    assert "Veg" in first.diets
    assert first.allergens == ["oat", "sulfur dioxide and sulfits"]
    assert first.prices["student"] == "3.10"


def test_import_replaces_days_in_the_feed_and_keeps_older_ones(exactum: Restaurant) -> None:
    before = Dish.objects.count()
    old = Dish.objects.create(restaurant=exactum, date=dt.date(2026, 11, 1), position=0, name="Old soup")
    feed = parse_feed(FIXTURE)
    feed[1].menuData.menus[0].data = feed[1].menuData.menus[0].data[:1]
    feed[1].menuData.menus.append(type(feed[1].menuData.menus[0])(date="someday"))

    stored = services.import_feed(feed, today=TODAY)

    assert stored == before - 2
    assert exactum.dishes.filter(date=MONDAY).count() == 1
    assert Dish.objects.filter(pk=old.pk).exists()
    assert Restaurant.objects.count() == 2


@respx.mock
def test_task_fetches_and_imports(db: None) -> None:
    respx.get(FEED_URL).mock(return_value=httpx.Response(200, json=FIXTURE))
    task = celery_app.tasks[fetch_menus.__module__ + ".fetch_menus"]
    assert task.apply().get() == Dish.objects.count() > 0


# REST API


def test_food_api_requires_login(api_client: APIClient) -> None:
    assert api_client.get("/api/food/restaurants/").status_code == 403
    assert api_client.get("/api/food/dishes/").status_code == 403


def test_dishes_can_be_filtered_by_day_and_restaurant(user_client: APIClient, exactum: Restaurant) -> None:
    response = user_client.get("/api/food/dishes/", {"date": "2026-11-16", "restaurant": exactum.pk})
    assert response.status_code == 200
    dishes = response.json()
    assert len(dishes) == 3
    assert dishes[0] == {
        "id": dishes[0]["id"],
        "restaurant": exactum.pk,
        "date": "2026-11-16",
        "name": "Chipotle sweet potato soup & avocado foam",
        "category": "Vegaanilounas",
        "diets": ["G", "KELA", "Veg", "Ilmastovalinta"],
        "allergens": ["oat", "sulfur dioxide and sulfits"],
        "prices": dishes[0]["prices"],
    }
    assert user_client.get("/api/food/dishes/", {"date": "2026-11-16"}).json() != dishes


def test_favourites_are_per_user(
    user: User,
    user_client: APIClient,
    other_client: APIClient,
    exactum: Restaurant,
) -> None:
    def favourites(client: APIClient) -> list[str]:
        return [item["name"] for item in client.get("/api/food/restaurants/").json() if item["is_favourite"]]

    url = f"/api/food/restaurants/{exactum.pk}/favourite/"
    assert user_client.put(url).status_code == 204
    assert user_client.put(url).status_code == 204
    assert favourites(user_client) == ["Exactum"]
    assert favourites(other_client) == []
    assert str(FavouriteRestaurant.objects.get()) == "Exactum"

    assert other_client.delete(url).status_code == 204
    assert favourites(user_client) == ["Exactum"]

    assert user_client.delete(url).status_code == 204
    assert favourites(user_client) == []
    assert user_client.put("/api/food/restaurants/0/favourite/").status_code == 404


# MCP


def test_menu_text_lists_favourites_compactly(user: User, exactum: Restaurant) -> None:
    services.set_favourite(user, exactum, favourite=True)
    assert services.menu_text(user, MONDAY).splitlines()[:3] == [
        "Mon 2026-11-16",
        "Exactum (Kumpula), lunch Mon–Fri 11.00-14.00, Sat–Sun Closed",
        "- Chipotle sweet potato soup & avocado foam [Vegaanilounas, G KELA Veg Ilmastovalinta] 3.10 €",
    ]


def test_menu_text_without_favourites_asks_for_a_restaurant(user: User, menus: None) -> None:
    assert (
        services.menu_text(user, MONDAY)
        == "No favourite restaurants. Name one of: Exactum, Olivia staff restaurant"
    )


def test_menu_text_finds_restaurants_by_part_of_the_name(user: User, menus: None) -> None:
    result = services.menu_text(user, MONDAY, "olivia")
    assert result.splitlines()[1].startswith("Olivia staff restaurant")
    assert "Exactum" not in result


def test_menu_text_reports_unknown_restaurants_and_empty_days(user: User, db: None) -> None:
    assert (
        services.menu_text(user, MONDAY, "x") == "No restaurant matches 'x'. Restaurants: (none loaded yet)"
    )
    Restaurant.objects.create(external_id=1, name="Bare")
    assert (
        services.menu_text(user, MONDAY, "bare") == "Mon 2026-11-16\nBare (), lunch hours unknown\n- no menu"
    )


def test_dish_line_omits_missing_details(db: None) -> None:
    restaurant = Restaurant.objects.create(external_id=1, name="Bare")
    Dish.objects.create(restaurant=restaurant, date=MONDAY, position=0, name="Porridge")
    assert "- Porridge\n" in services.menu_text(User(pk=0), MONDAY, "bare") + "\n"


@pytest.mark.django_db(transaction=True)
def test_food_tool_needs_the_food_scope(server: TestClient, user: User) -> None:
    assert food_mcp.food_menu.__name__ in tool_names(server, token_for(user, {"food": "read"}))
    other = User.objects.create_user("carol")
    assert "food_menu" not in tool_names(server, token_for(other, {"sleep": "read"}))


@pytest.mark.django_db(transaction=True)
def test_food_tool_returns_menus_and_explains_bad_dates(server: TestClient, user: User) -> None:
    services.import_feed(parse_feed(FIXTURE), today=TODAY)
    token = token_for(user, {"food": "read"})
    result = text(call(server, token, "food_menu", {"date": "2026-11-16", "restaurant": "exactum"}))
    assert result.startswith("Mon 2026-11-16\nExactum (Kumpula)")
    assert (
        text(call(server, token, "food_menu", {"date": "16.11."})) == "Invalid date '16.11.'. Use YYYY-MM-DD."
    )
    assert text(call(server, token, "food_menu")).startswith("No favourite restaurants.")
