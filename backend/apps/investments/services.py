"""Fetching prices and valuing holdings."""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Max
from django.utils import timezone

from apps.accounts.models import User
from apps.investments import providers
from apps.investments.models import Asset, FxRate, Holding, PricePoint

#: How much history is fetched when an asset is first added.
INITIAL_HISTORY = dt.timedelta(days=365 * 2)
CENT = Decimal("0.01")
EUR = "EUR"


def get_or_create_asset(provider: str, symbol: str) -> Asset:
    """Return the asset with ``symbol`` at ``provider``, fetching its history if it is new.

    Raises :class:`providers.UnknownAssetError` when the provider does not know the symbol.
    """
    symbol = symbol.strip().lower() if provider == "coingecko" else symbol.strip().upper()
    existing = Asset.objects.filter(provider=provider, symbol=symbol).first()
    if existing:
        return existing
    start = timezone.localdate() - INITIAL_HISTORY
    history = providers.HISTORY[provider](symbol, start)
    asset = Asset.objects.create(
        provider=provider, symbol=symbol, name=history.name, currency=history.currency
    )
    _store_prices(asset, history.prices)
    update_fx_rates()
    return asset


def _store_prices(asset: Asset, prices: dict[dt.date, Decimal]) -> None:
    PricePoint.objects.bulk_create(
        [PricePoint(asset=asset, date=day, close=close) for day, close in prices.items()],
        update_conflicts=True,
        unique_fields=["asset", "date"],
        update_fields=["close"],
    )


def update_prices() -> int:
    """Fetch new prices for every asset that somebody holds. Returns how many assets were updated.

    An asset whose prices cannot be fetched is skipped and retried on the next run.
    """
    updated = 0
    for asset in Asset.objects.filter(holdings__isnull=False).distinct():
        # The latest day is fetched again, as its price may have been taken before the market closed.
        latest = asset.prices.aggregate(latest=Max("date"))["latest"]
        start = latest or timezone.localdate() - INITIAL_HISTORY
        try:
            history = providers.HISTORY[asset.provider](asset.symbol, start)
        except Exception:  # noqa: BLE001, S112 - the next run retries
            continue
        _store_prices(asset, history.prices)
        updated += 1
    update_fx_rates()
    return updated


def update_fx_rates() -> None:
    """Fetch the exchange rates of every non-euro currency that an asset is priced in."""
    currencies = sorted(set(Asset.objects.exclude(currency=EUR).values_list("currency", flat=True)))
    if not currencies:
        return
    latest = FxRate.objects.aggregate(latest=Max("date"))["latest"]
    missing = [currency for currency in currencies if not FxRate.objects.filter(currency=currency).exists()]
    start = timezone.localdate() - INITIAL_HISTORY if missing or latest is None else latest
    rates = providers.fx_rates(currencies, start)
    FxRate.objects.bulk_create(
        [FxRate(currency=currency, date=day, rate=rate) for (currency, day), rate in rates.items()],
        update_conflicts=True,
        unique_fields=["currency", "date"],
        update_fields=["rate"],
    )


def _to_eur(amount: Decimal, currency: str, day: dt.date) -> Decimal | None:
    """Convert ``amount`` to euros with the latest rate on or before ``day``."""
    if currency == EUR:
        return amount
    rate = FxRate.objects.filter(currency=currency, date__lte=day).order_by("-date").first()
    return amount / rate.rate if rate else None


@dataclass(frozen=True)
class Position:
    """A holding with its latest price. Values are ``None`` when no price or exchange rate is known."""

    holding: Holding
    price: Decimal | None
    price_date: dt.date | None
    value_eur: Decimal | None

    @property
    def gain_eur(self) -> Decimal | None:
        """Value minus cost, when both are known."""
        if self.value_eur is None or self.holding.cost is None:
            return None
        return self.value_eur - self.holding.cost


@dataclass(frozen=True)
class Portfolio:
    """The holdings of a user and their total value."""

    positions: list[Position]

    @property
    def total_eur(self) -> Decimal:
        """Sum of the positions whose value is known."""
        return sum(
            (position.value_eur for position in self.positions if position.value_eur is not None), Decimal(0)
        )


def portfolio(user: User) -> Portfolio:
    """Return the holdings of ``user`` valued at the latest known prices."""
    positions: list[Position] = []
    for holding in Holding.objects.for_user(user).select_related("asset"):
        latest = holding.asset.prices.order_by("-date").first()
        value = None
        if latest:
            value = _to_eur(holding.quantity * latest.close, holding.asset.currency, latest.date)
        positions.append(
            Position(
                holding=holding,
                price=latest.close if latest else None,
                price_date=latest.date if latest else None,
                value_eur=value.quantize(CENT) if value is not None else None,
            ),
        )
    return Portfolio(positions)


def value_history(user: User, first: dt.date, last: dt.date) -> list[tuple[dt.date, Decimal]]:
    """Return the total euro value of the current holdings of ``user`` on each day with a price.

    Today's quantities are applied to past prices, as trades are not recorded:
    the series shows how the present portfolio would have developed.
    """
    holdings = list(Holding.objects.for_user(user).select_related("asset"))
    days = sorted(
        set(
            PricePoint.objects.filter(
                asset__holdings__user=user, date__gte=first, date__lte=last
            ).values_list("date", flat=True)
        ),
    )
    series: list[tuple[dt.date, Decimal]] = []
    for day in days:
        total = Decimal(0)
        for holding in holdings:
            price = holding.asset.prices.filter(date__lte=day).order_by("-date").first()
            value = _to_eur(holding.quantity * price.close, holding.asset.currency, day) if price else None
            total += value or Decimal(0)
        series.append((day, total.quantize(CENT)))
    return series


def portfolio_text(user: User) -> str:
    """Return the portfolio of ``user`` as compact text for an AI agent."""
    result = portfolio(user)
    if not result.positions:
        return "No holdings."
    lines = [
        f"Portfolio total {result.total_eur:.2f} EUR",
        "quantity symbol (name): price, value EUR, gain EUR",
    ]
    for position in result.positions:
        asset = position.holding.asset
        price = "no price"
        if position.price is not None:
            price = f"{position.price.normalize():f} {asset.currency} on {position.price_date}"
        value = f"{position.value_eur:.2f}" if position.value_eur is not None else "?"
        gain = f"{position.gain_eur:+.2f}" if position.gain_eur is not None else "-"
        quantity = f"{position.holding.quantity.normalize():f}"
        lines.append(f"{quantity} {asset.symbol} ({asset.name}): {price}, {value}, {gain}")
    return "\n".join(lines)


def prices_text(symbol: str, days: int) -> str:
    """Return the recent closing prices of an asset as compact text for an AI agent."""
    asset = Asset.objects.filter(symbol__iexact=symbol.strip()).first()
    if asset is None:
        known = ", ".join(Asset.objects.values_list("symbol", flat=True)) or "(none)"
        return f"No asset {symbol!r}. Known assets: {known}"
    prices = list(asset.prices.filter(date__gte=timezone.localdate() - dt.timedelta(days=days)))
    if not prices:
        return f"No prices for {asset.symbol} in the last {days} days."
    lines = [f"{asset.symbol} ({asset.name}) closing prices, {asset.currency}"]
    lines += [f"{price.date} {price.close.normalize():f}" for price in prices]
    return "\n".join(lines)
