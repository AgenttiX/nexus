"""Tests for the investments app."""

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal

import httpx
import pandas as pd
import pytest
import respx
from django.utils import timezone
from rest_framework.test import APIClient
from starlette.testclient import TestClient

from apps.accounts.models import AgentToken, User
from apps.investments import providers, services, tasks
from apps.investments.models import Asset, FxRate, Holding, PricePoint
from tests.isolation import assert_hidden_from
from tests.mcp_helpers import call, text, tool_names

TODAY = timezone.localdate()
YESTERDAY = TODAY - dt.timedelta(days=1)
COINGECKO = providers.COINGECKO_URL.format(symbol="bitcoin")


class FakeTicker:
    """Stands in for ``yfinance.Ticker``: two days of closes for known symbols, nothing for others."""

    closes: dict[str, list[float]] = {"NOKIA.HE": [7.0, 7.5], "AAPL": [200.0, float("nan")]}
    infos: dict[str, dict[str, str] | None] = {
        "NOKIA.HE": {"shortName": "Nokia Corporation", "currency": "EUR"},
        "AAPL": {"longName": "Apple Inc.", "currency": "usd"},
    }
    calls: list[tuple[str, str]] = []

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol

    def history(self, start: str, auto_adjust: bool) -> pd.DataFrame:  # noqa: FBT001
        self.calls.append((self.symbol, start))
        closes = self.closes.get(self.symbol, [])
        index = pd.DatetimeIndex([pd.Timestamp(YESTERDAY), pd.Timestamp(TODAY)][: len(closes)])
        return pd.DataFrame({"Close": closes}, index=index)

    @property
    def info(self) -> dict[str, str] | None:
        return self.infos.get(self.symbol)


@pytest.fixture(autouse=True)
def yahoo(monkeypatch: pytest.MonkeyPatch) -> type[FakeTicker]:
    monkeypatch.setattr(FakeTicker, "calls", [])
    monkeypatch.setattr(FakeTicker, "closes", dict(FakeTicker.closes))
    monkeypatch.setattr(FakeTicker, "infos", dict(FakeTicker.infos))
    monkeypatch.setattr(providers.yfinance, "Ticker", FakeTicker)
    return FakeTicker


@pytest.fixture
def network() -> Iterator[respx.MockRouter]:
    """CoinGecko with two days of bitcoin prices, and ECB rates of 2 USD per euro."""
    stamps = [dt.datetime.combine(day, dt.time(), dt.UTC).timestamp() * 1000 for day in (YESTERDAY, TODAY)]
    with respx.mock(assert_all_called=False) as router:
        router.get(COINGECKO).mock(
            return_value=httpx.Response(200, json={"prices": [[stamps[0], 50000.0], [stamps[1], 52000.5]]}),
        )
        router.get(url__startswith="https://api.frankfurter.dev/v1/").mock(
            return_value=httpx.Response(200, json={"rates": {YESTERDAY.isoformat(): {"USD": 2.0}}}),
        )
        yield router


def hold(user: User, provider: str, symbol: str, quantity: str, cost: str | None = None) -> Holding:
    asset = services.get_or_create_asset(provider, symbol)
    return Holding.objects.create(
        user=user, asset=asset, quantity=Decimal(quantity), cost=cost and Decimal(cost)
    )


# Providers


def test_yahoo_history_skips_missing_closes() -> None:
    history = providers.yahoo_history("AAPL", YESTERDAY)
    assert (history.name, history.currency, history.prices) == (
        "Apple Inc.",
        "USD",
        {YESTERDAY: Decimal(200)},
    )
    with pytest.raises(providers.UnknownAssetError):
        providers.yahoo_history("NOSUCH", YESTERDAY)


def test_float_noise_is_dropped_from_prices(yahoo: type[FakeTicker], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(yahoo.closes, "NOKIA.HE", [7.072000026702881])
    assert providers.yahoo_history("NOKIA.HE", YESTERDAY).prices == {YESTERDAY: Decimal("7.072")}


def test_yahoo_history_without_details_uses_the_symbol(
    yahoo: type[FakeTicker], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(yahoo.infos, "NOKIA.HE", None)
    history = providers.yahoo_history("NOKIA.HE", YESTERDAY)
    assert (history.name, history.currency) == ("NOKIA.HE", "EUR")


def test_coingecko_history(network: respx.MockRouter, settings: object) -> None:
    history = providers.coingecko_history("bitcoin", YESTERDAY)
    assert history.prices == {YESTERDAY: Decimal(50000), TODAY: Decimal("52000.5")}
    assert history.currency == "EUR"
    request = network.calls.last.request
    assert dict(request.url.params) == {"vs_currency": "eur", "days": "1", "interval": "daily"}
    assert "x-cg-demo-api-key" not in request.headers


def test_coingecko_asks_for_at_most_a_year(network: respx.MockRouter) -> None:
    providers.coingecko_history("bitcoin", TODAY - dt.timedelta(days=730))
    assert network.calls.last.request.url.params["days"] == "365"


def test_coingecko_uses_the_demo_key_when_set(network: respx.MockRouter, settings: object) -> None:
    settings.COINGECKO_API_KEY = "demo"  # type: ignore[attr-defined]
    providers.coingecko_history("bitcoin", TODAY)
    assert network.calls.last.request.headers["x-cg-demo-api-key"] == "demo"


@respx.mock
def test_coingecko_reports_unknown_coins_and_errors() -> None:
    respx.get(providers.COINGECKO_URL.format(symbol="nosuch")).mock(return_value=httpx.Response(404))
    with pytest.raises(providers.UnknownAssetError):
        providers.coingecko_history("nosuch", YESTERDAY)
    respx.get(providers.COINGECKO_URL.format(symbol="empty")).mock(
        return_value=httpx.Response(200, json={"prices": []})
    )
    with pytest.raises(providers.UnknownAssetError):
        providers.coingecko_history("empty", YESTERDAY)
    respx.get(providers.COINGECKO_URL.format(symbol="busy")).mock(return_value=httpx.Response(429))
    with pytest.raises(httpx.HTTPStatusError):
        providers.coingecko_history("busy", YESTERDAY)


def test_fx_rates(network: respx.MockRouter) -> None:
    assert providers.fx_rates(["USD"], YESTERDAY) == {("USD", YESTERDAY): Decimal(2)}


# Assets and prices


def test_new_asset_gets_its_history_and_is_shared(
    user: User, other_user: User, network: respx.MockRouter
) -> None:
    first = hold(user, "yahoo", " nokia.he ", "100")
    second = hold(other_user, "yahoo", "NOKIA.HE", "5")
    assert first.asset == second.asset
    assert Asset.objects.count() == 1
    assert (first.asset.name, first.asset.currency, str(first.asset)) == (
        "Nokia Corporation",
        "EUR",
        "NOKIA.HE",
    )
    assert list(first.asset.prices.values_list("date", "close")) == [
        (YESTERDAY, Decimal(7)),
        (TODAY, Decimal("7.5")),
    ]
    assert len(FakeTicker.calls) == 1
    assert hold(user, "coingecko", "Bitcoin", "0.1").asset.symbol == "bitcoin"
    assert not FxRate.objects.exists()
    assert str(first) == "100 NOKIA.HE"
    assert str(first.asset.prices.first()) == f"NOKIA.HE {YESTERDAY} 7.00000000"


def test_update_refreshes_held_assets_only(
    user: User, network: respx.MockRouter, yahoo: type[FakeTicker]
) -> None:
    hold(user, "yahoo", "NOKIA.HE", "100")
    hold(user, "yahoo", "AAPL", "1")
    services.get_or_create_asset("coingecko", "bitcoin")
    yahoo.closes = {**yahoo.closes, "NOKIA.HE": [7.0, 8.0]}
    yahoo.calls = []

    assert tasks.update_prices.apply().get() == 2
    assert sorted(yahoo.calls) == [("AAPL", YESTERDAY.isoformat()), ("NOKIA.HE", TODAY.isoformat())]
    assert PricePoint.objects.get(asset__symbol="NOKIA.HE", date=TODAY).close == Decimal(8)
    assert str(FxRate.objects.get()) == f"USD {YESTERDAY} 2.00000000"


def test_update_survives_a_failing_provider(
    user: User, network: respx.MockRouter, yahoo: type[FakeTicker]
) -> None:
    hold(user, "yahoo", "NOKIA.HE", "100")
    hold(user, "coingecko", "bitcoin", "1")
    yahoo.closes = {}
    assert services.update_prices() == 1


def test_asset_without_prices_is_fetched_from_the_beginning(user: User, network: respx.MockRouter) -> None:
    holding = hold(user, "yahoo", "NOKIA.HE", "1")
    holding.asset.prices.all().delete()
    FakeTicker.calls = []
    services.update_prices()
    assert FakeTicker.calls == [("NOKIA.HE", (TODAY - services.INITIAL_HISTORY).isoformat())]


# Valuation


def test_portfolio_values_holdings_in_euros(user: User, other_user: User, network: respx.MockRouter) -> None:
    hold(user, "yahoo", "NOKIA.HE", "100", cost="500")
    hold(user, "yahoo", "AAPL", "2")
    hold(other_user, "coingecko", "bitcoin", "1")
    result = services.portfolio(user)
    nokia, apple = sorted(result.positions, key=lambda position: position.holding.asset.symbol, reverse=True)
    assert (nokia.price, nokia.price_date, nokia.value_eur, nokia.gain_eur) == (
        Decimal("7.5"),
        TODAY,
        Decimal("750.00"),
        Decimal("250.00"),
    )
    assert (apple.value_eur, apple.gain_eur) == (Decimal("200.00"), None)
    assert result.total_eur == Decimal("950.00")
    assert services.portfolio(other_user).total_eur == Decimal("52000.50")


def test_positions_without_price_or_rate_have_no_value(user: User, network: respx.MockRouter) -> None:
    hold(user, "yahoo", "AAPL", "2", cost="100")
    FxRate.objects.all().delete()
    empty = Asset.objects.create(provider="yahoo", symbol="NEW", currency="EUR")
    Holding.objects.create(user=user, asset=empty, quantity=1)
    result = services.portfolio(user)
    assert [(position.price, position.value_eur, position.gain_eur) for position in result.positions] == [
        (Decimal(200), None, None),
        (None, None, None),
    ]
    assert result.total_eur == 0
    assert services.portfolio_text(user).splitlines()[2:] == [
        f"2 AAPL (Apple Inc.): 200 USD on {YESTERDAY}, ?, -",
        "1 NEW (): no price, ?, -",
    ]


def test_value_history_applies_current_holdings_to_past_prices(user: User, network: respx.MockRouter) -> None:
    hold(user, "yahoo", "NOKIA.HE", "100")
    hold(user, "yahoo", "AAPL", "2")
    assert services.value_history(user, YESTERDAY, TODAY) == [
        (YESTERDAY, Decimal("900.00")),
        (TODAY, Decimal("950.00")),
    ]
    assert services.value_history(user, TODAY + dt.timedelta(days=1), TODAY + dt.timedelta(days=2)) == []


def test_history_ignores_assets_without_earlier_prices(user: User, network: respx.MockRouter) -> None:
    hold(user, "yahoo", "NOKIA.HE", "100")
    late = Asset.objects.create(provider="yahoo", symbol="LATE", currency="EUR")
    PricePoint.objects.create(asset=late, date=TODAY, close=1)
    Holding.objects.create(user=user, asset=late, quantity=10)
    assert services.value_history(user, YESTERDAY, TODAY) == [
        (YESTERDAY, Decimal("700.00")),
        (TODAY, Decimal("760.00")),
    ]


def test_portfolio_and_price_texts(user: User, other_user: User, network: respx.MockRouter) -> None:
    hold(user, "yahoo", "NOKIA.HE", "100", cost="500")
    assert services.portfolio_text(user) == (
        "Portfolio total 750.00 EUR\n"
        "quantity symbol (name): price, value EUR, gain EUR\n"
        f"100 NOKIA.HE (Nokia Corporation): 7.5 EUR on {TODAY}, 750.00, +250.00"
    )
    assert services.portfolio_text(other_user) == "No holdings."
    assert services.prices_text("nokia.he", 30) == (
        f"NOKIA.HE (Nokia Corporation) closing prices, EUR\n{YESTERDAY} 7\n{TODAY} 7.5"
    )
    assert services.prices_text("TSLA", 30) == "No asset 'TSLA'. Known assets: NOKIA.HE"
    PricePoint.objects.all().delete()
    assert services.prices_text("NOKIA.HE", 30) == "No prices for NOKIA.HE in the last 30 days."
    Holding.objects.all().delete()
    Asset.objects.all().delete()
    assert services.prices_text("X", 30) == "No asset 'X'. Known assets: (none)"


# REST API


def test_investments_api_requires_login(api_client: APIClient) -> None:
    assert api_client.get("/api/investments/holdings/").status_code == 403
    assert api_client.get("/api/investments/portfolio/").status_code == 403


def test_holdings_can_be_created_changed_and_removed(
    user_client: APIClient, network: respx.MockRouter
) -> None:
    new = {"provider": "yahoo", "symbol": "nokia.he", "quantity": "100", "cost": "500.00", "note": "Broker"}
    created = user_client.post("/api/investments/holdings/", new, format="json")
    assert created.status_code == 201
    body = created.json()
    assert body["asset"] == {
        "id": body["asset"]["id"],
        "provider": "yahoo",
        "symbol": "NOKIA.HE",
        "name": "Nokia Corporation",
        "currency": "EUR",
    }
    assert ("provider" in body, body["quantity"]) == (False, "100.00000000")

    changed = user_client.patch(
        f"/api/investments/holdings/{body['id']}/", {"quantity": "150", "symbol": "AAPL"}, format="json"
    )
    assert (changed.status_code, changed.json()["quantity"], changed.json()["asset"]["symbol"]) == (
        200,
        "150.00000000",
        "NOKIA.HE",
    )
    assert user_client.delete(f"/api/investments/holdings/{body['id']}/").status_code == 204


def test_bad_holdings_are_rejected(user_client: APIClient, network: respx.MockRouter) -> None:
    def post(**data: str) -> tuple[int, list[str]]:
        response = user_client.post("/api/investments/holdings/", {"quantity": "1", **data}, format="json")
        return response.status_code, list(response.json())

    assert post(provider="yahoo", symbol="NOSUCH") == (400, ["symbol"])
    assert post(provider="coingecko", symbol="unreachable") == (400, ["symbol"])
    assert post(provider="yahoo") == (400, ["non_field_errors"])
    assert post(provider="bank", symbol="X") == (400, ["provider"])
    assert post(provider="yahoo", symbol="NOKIA.HE", quantity="-1") == (400, ["quantity"])
    assert not Holding.objects.exists()


def test_portfolio_api(
    user_client: APIClient, other_client: APIClient, user: User, network: respx.MockRouter
) -> None:
    holding = hold(user, "yahoo", "NOKIA.HE", "100", cost="500")
    body = user_client.get("/api/investments/portfolio/").json()
    assert body["total_eur"] == "750.00"
    position = body["positions"][0]
    assert (position["holding"]["id"], position["price"], position["value_eur"], position["gain_eur"]) == (
        holding.pk,
        "7.50000000",
        "750.00",
        "250.00",
    )
    assert position["price_date"] == TODAY.isoformat()
    assert body["history"] == [
        {"date": YESTERDAY.isoformat(), "value_eur": "700.00"},
        {"date": TODAY.isoformat(), "value_eur": "750.00"},
    ]
    assert other_client.get("/api/investments/portfolio/").json() == {
        "total_eur": "0.00",
        "positions": [],
        "history": [],
    }
    assert_hidden_from(other_client, "/api/investments/holdings/", holding.pk)


# MCP


@pytest.mark.django_db(transaction=True)
def test_investment_tools(server: TestClient, user: User, network: respx.MockRouter) -> None:
    hold(user, "yahoo", "NOKIA.HE", "100")
    outsider = AgentToken.objects.create_token(user, "finance agent", {"finance": "read"})[1]
    assert not {"portfolio", "asset_prices"} & tool_names(server, outsider)
    token = AgentToken.objects.create_token(user, "investment agent", {"investments": "read"})[1]
    assert text(call(server, token, "portfolio")).startswith("Portfolio total 750.00 EUR")
    assert text(call(server, token, "asset_prices", {"symbol": "NOKIA.HE"})).endswith(f"{TODAY} 7.5")
    assert text(call(server, token, "asset_prices", {"symbol": "NOKIA.HE", "days": 100000})).count("\n") == 2
