"""Client for the menu feed of UniCafe.

The feed is the JSON that UniCafe's own website loads. It is undocumented, so
everything read from it is validated and anything unexpected is skipped.
"""

import datetime as dt
import re

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

FEED_URL = "https://unicafe.fi/wp-json/swiss/v1/restaurants/"
TIMEOUT_SECONDS = 30
DATE_PATTERN = re.compile(r"(\d{1,2})\.(\d{1,2})\.")


class FeedPrice(BaseModel):
    """Price of a dish: a category name and euros per customer group."""

    name: str = ""
    value: dict[str, str] = Field(default_factory=dict)

    @field_validator("value", mode="before")
    @classmethod
    def empty_list_means_no_prices(cls, value: object) -> object:
        """Accept the empty list that the feed sends for a dish without prices."""
        return {} if value == [] else value


class FeedDish(BaseModel):
    """A dish as the feed gives it."""

    name: str
    meta: dict[str, list[str]] = Field(default_factory=dict)
    price: FeedPrice = Field(default_factory=FeedPrice)


class FeedDay(BaseModel):
    """The dishes of one day. The date has a weekday, day and month, but no year."""

    date: str
    data: list[FeedDish] = Field(default_factory=list)


class FeedHourItem(BaseModel):
    """Opening hours for a range of weekdays."""

    label: str = ""
    hours: str = ""


class FeedHours(BaseModel):
    """One kind of opening hours, such as lunch."""

    items: list[FeedHourItem] = Field(default_factory=list)


class FeedMenuData(BaseModel):
    """Menus and opening hours of a restaurant. Unused kinds of hours are ``False`` in the feed."""

    visitingHours: dict[str, FeedHours | bool] = Field(default_factory=dict)  # noqa: N815 - name in the feed
    menus: list[FeedDay] = Field(default_factory=list)


class FeedLocation(BaseModel):
    """A campus."""

    name: str = ""


class FeedRestaurant(BaseModel):
    """A restaurant as the feed gives it."""

    id: int
    title: str
    permalink: str = ""
    address: str = ""
    location: list[FeedLocation] = Field(default_factory=list)
    menuData: FeedMenuData = Field(default_factory=FeedMenuData)  # noqa: N815 - name in the feed

    @property
    def campus(self) -> str:
        """Return the name of the restaurant's campus, if any."""
        return self.location[0].name if self.location else ""

    @property
    def lunch_hours(self) -> str:
        """Return lunch hours, or general opening hours when lunch has none, as one line."""
        hours = self.menuData.visitingHours
        for kind in ("lounas", "business"):
            entry = hours.get(kind)
            if isinstance(entry, FeedHours) and entry.items:
                return ", ".join(f"{item.label} {item.hours}".strip() for item in entry.items)
        return ""


def fetch_feed(language: str = "en") -> list[FeedRestaurant]:
    """Download the feed and return the restaurants that could be understood."""
    response = httpx.get(FEED_URL, params={"lang": language}, timeout=TIMEOUT_SECONDS, follow_redirects=True)
    response.raise_for_status()
    return parse_feed(response.json())


def parse_feed(payload: object) -> list[FeedRestaurant]:
    """Validate a decoded feed, skipping entries that do not look like restaurants."""
    if not isinstance(payload, list):
        msg = "The UniCafe feed is not a list of restaurants."
        raise TypeError(msg)
    restaurants: list[FeedRestaurant] = []
    for item in payload:
        try:
            restaurants.append(FeedRestaurant.model_validate(item))
        except ValidationError:
            continue
    return restaurants


def parse_date(text: str, today: dt.date) -> dt.date | None:
    """Turn a feed date such as ``Mon 16.11.`` into a date.

    The feed leaves out the year, so the year that puts the date closest to
    ``today`` is used. That stays right across the turn of the year.
    """
    match = DATE_PATTERN.search(text)
    if match is None:
        return None
    day, month = int(match.group(1)), int(match.group(2))
    candidates: list[dt.date] = []
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            candidates.append(dt.date(year, month, day))
        except ValueError:
            continue
    return min(candidates, key=lambda candidate: abs((candidate - today).days), default=None)
