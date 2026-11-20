"""Sources of market prices and exchange rates. All are free to use.

- Yahoo Finance, through the ``yfinance`` library, for stocks, ETFs and funds,
  including Nasdaq Helsinki (tickers ending in ``.HE``). Yahoo has no official
  API; its terms allow personal use.
- CoinGecko's public API for cryptocurrencies, priced in euros. A free demo key
  (``COINGECKO_API_KEY``) raises the rate limit but is not required.
- Frankfurter, which serves the European Central Bank's reference rates.
"""

import datetime as dt
import math
from dataclasses import dataclass
from decimal import Decimal

import httpx
import yfinance
from django.conf import settings

TIMEOUT_SECONDS = 30
COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/{symbol}/market_chart"
FRANKFURTER_URL = "https://api.frankfurter.dev/v1/{start}.."
PRICE_DIGITS = 6
#: CoinGecko's free API serves at most the past year.
COINGECKO_MAX_DAYS = 365


@dataclass(frozen=True)
class History:
    """Daily closing prices of an asset, in ``currency``."""

    name: str
    currency: str
    prices: dict[dt.date, Decimal]


class UnknownAssetError(LookupError):
    """Raised when a provider has no asset with the requested symbol."""


def _decimal(value: float) -> Decimal:
    """Convert a provider's float to a decimal, dropping the noise that single-precision floats carry."""
    return Decimal(str(round(value, PRICE_DIGITS)))


def yahoo_history(symbol: str, start: dt.date) -> History:
    """Return the daily closes of a Yahoo Finance ticker since ``start``."""
    ticker = yfinance.Ticker(symbol)
    frame = ticker.history(start=start.isoformat(), auto_adjust=False)
    prices = {
        moment.date(): _decimal(float(close))
        for moment, close in frame["Close"].items()
        if not math.isnan(float(close))
    }
    if not prices:
        raise UnknownAssetError(symbol)
    info = ticker.info or {}
    return History(
        name=str(info.get("shortName") or info.get("longName") or symbol),
        currency=str(info.get("currency") or "EUR").upper()[:3],
        prices=prices,
    )


def coingecko_history(symbol: str, start: dt.date) -> History:
    """Return the daily euro prices of a CoinGecko coin since ``start``. The last one is the current price."""
    days = min(max((dt.datetime.now(tz=dt.UTC).date() - start).days, 1), COINGECKO_MAX_DAYS)
    headers = {"x-cg-demo-api-key": settings.COINGECKO_API_KEY} if settings.COINGECKO_API_KEY else {}
    response = httpx.get(
        COINGECKO_URL.format(symbol=symbol),
        params={"vs_currency": "eur", "days": days, "interval": "daily"},
        headers=headers,
        timeout=TIMEOUT_SECONDS,
    )
    if response.status_code == httpx.codes.NOT_FOUND:
        raise UnknownAssetError(symbol)
    response.raise_for_status()
    prices = {
        dt.datetime.fromtimestamp(milliseconds / 1000, tz=dt.UTC).date(): _decimal(price)
        for milliseconds, price in response.json()["prices"]
    }
    if not prices:
        raise UnknownAssetError(symbol)
    return History(name=symbol, currency="EUR", prices=prices)


def fx_rates(currencies: list[str], start: dt.date) -> dict[tuple[str, dt.date], Decimal]:
    """Return the ECB reference rates (units of currency per euro) of ``currencies`` since ``start``."""
    response = httpx.get(
        FRANKFURTER_URL.format(start=start.isoformat()),
        params={"base": "EUR", "symbols": ",".join(currencies)},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return {
        (currency, dt.date.fromisoformat(day)): _decimal(rate)
        for day, rates in response.json()["rates"].items()
        for currency, rate in rates.items()
    }


HISTORY = {"yahoo": yahoo_history, "coingecko": coingecko_history}
