"""Assets, their prices, and each user's holdings.

Assets, prices and exchange rates are public and shared by all users, so that
the price history of an asset is stored once however many users hold it. Only
holdings are user-owned.
"""

from typing import ClassVar

from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import OwnedManager, OwnedModel


class Provider(models.TextChoices):
    """Where the prices of an asset come from."""

    YAHOO = "yahoo", "Yahoo Finance (stocks, ETFs and funds)"
    COINGECKO = "coingecko", "CoinGecko (cryptocurrencies)"


class Asset(models.Model):
    """Something that can be invested in and has a market price."""

    provider = models.CharField(max_length=20, choices=Provider.choices)
    symbol = models.CharField(
        max_length=50,
        help_text="The provider's identifier: a ticker such as NOKIA.HE, or a CoinGecko id such as bitcoin.",
    )
    name = models.CharField(max_length=200, blank=True)
    currency = models.CharField(max_length=3, help_text="The currency of the stored prices.")

    class Meta:
        ordering = ("symbol",)
        constraints = (models.UniqueConstraint(fields=("provider", "symbol"), name="unique_asset"),)

    def __str__(self) -> str:
        """Return the asset's symbol."""
        return self.symbol


class PricePoint(models.Model):
    """The closing price of an asset on one day."""

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="prices")
    date = models.DateField()
    close = models.DecimalField(max_digits=20, decimal_places=8)

    class Meta:
        ordering = ("date",)
        constraints = (models.UniqueConstraint(fields=("asset", "date"), name="unique_price_point"),)

    def __str__(self) -> str:
        """Return the asset, day and price."""
        return f"{self.asset} {self.date} {self.close}"


class FxRate(models.Model):
    """The European Central Bank's reference rate of a currency on one day: units of it per euro."""

    currency = models.CharField(max_length=3)
    date = models.DateField()
    rate = models.DecimalField(max_digits=20, decimal_places=8)

    class Meta:
        ordering = ("date",)
        constraints = (models.UniqueConstraint(fields=("currency", "date"), name="unique_fx_rate"),)

    def __str__(self) -> str:
        """Return the currency, day and rate."""
        return f"{self.currency} {self.date} {self.rate}"


class Holding(OwnedModel):
    """An amount of an asset that a user owns."""

    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="holdings")
    quantity = models.DecimalField(max_digits=20, decimal_places=8, validators=[MinValueValidator(0)])
    cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="What the holding cost in total, in euros. Optional; used to show the gain.",
    )
    note = models.CharField(max_length=200, blank=True, help_text="For example the broker or account.")

    objects: ClassVar[OwnedManager[Holding]] = OwnedManager()

    class Meta(OwnedModel.Meta):
        ordering = ("asset__symbol", "id")

    def __str__(self) -> str:
        """Return the quantity and the asset."""
        return f"{self.quantity.normalize():f} {self.asset}"
