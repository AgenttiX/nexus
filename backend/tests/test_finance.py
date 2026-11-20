"""Tests for the finance app."""

import datetime as dt
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from starlette.testclient import TestClient

from apps.accounts.models import AgentToken, User
from apps.finance import importers, services
from apps.finance.models import BankAccount, Category, Transaction, validate_iban
from tests.isolation import assert_hidden_from
from tests.mcp_helpers import call, text, tool_names

IBAN = "FI2112345600000785"
OTHER_IBAN = "DE89370400440532013000"
CSV = b"""date,amount,counterparty,message,reference
2026-10-01,2500.00,Employer Ltd,Salary,
2026-10-03,-45.90,Grocer,,123
2026-10-03,-45.90,Grocer,,123
2026-10-15,-800.00,Landlord,Rent October,RF18
2026-11-02,-12.50,Cafe,Lunch,
"""
OCTOBER = (dt.date(2026, 10, 1), dt.date(2026, 10, 31))
BOTH = (dt.date(2026, 10, 1), dt.date(2026, 11, 30))


@pytest.fixture
def account(user: User) -> BankAccount:
    return BankAccount.objects.create(user=user, name="Everyday", iban=IBAN)


@pytest.fixture
def imported(account: BankAccount) -> BankAccount:
    """An account with the transactions of ``CSV``, rent categorised as housing."""
    services.import_file(account, "october.csv", CSV)
    housing = Category.objects.create(user=account.user, name="Housing")
    account.transactions.filter(counterparty="Landlord").update(category=housing)
    return account


def upload(
    client: APIClient, account: BankAccount, data: bytes, name: str = "export.csv"
) -> tuple[int, dict[str, object]]:
    file = SimpleUploadedFile(name, data, content_type="text/csv")
    response = client.post(f"/api/finance/accounts/{account.pk}/import/", {"file": file}, format="multipart")
    return response.status_code, response.json()


# Validation and reading files


@pytest.mark.parametrize(
    "value", ["FI2112345600000786", "fi2112345600000785", "FI21 1234 5600 0007 85", "hello"]
)
def test_invalid_or_unnormalised_ibans_are_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        validate_iban(value)
    validate_iban(IBAN)


def test_generic_csv_is_read() -> None:
    rows = importers.read_generic(CSV.decode())
    assert len(rows) == 5
    assert rows[0] == importers.Row(dt.date(2026, 10, 1), Decimal("2500.00"), "Employer Ltd", "Salary", "")
    assert importers.read_generic("date,amount\n2026-10-01,5\n") == [
        importers.Row(dt.date(2026, 10, 1), Decimal(5))
    ]


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("when,how much\n2026-10-01,5\n", "header row"),
        ("", "header row"),
        ("date,amount\n1.10.2026,5\n", "Line 2"),
        ("date,amount\n2026-10-01,5\n2026-10-02,five\n", "Line 3"),
        ("date,amount\n2026-10-01\n", "Line 2"),
    ],
)
def test_unreadable_csv_is_explained(content: str, message: str) -> None:
    with pytest.raises(importers.ImportError_, match=message):
        importers.read_generic(content)


def test_files_are_decoded_as_utf8_or_latin1() -> None:
    assert services.decode("﻿date,amount\nÄ".encode()) == "date,amount\nÄ"
    assert services.decode("Ä".encode("latin-1")) == "Ä"
    with pytest.raises(importers.ImportError_, match="too large"):
        services.decode(b"x" * (services.MAX_FILE_BYTES + 1))


# Import


def test_import_stores_rows_and_skips_what_was_imported_before(account: BankAccount) -> None:
    first = services.import_file(account, "october.csv", CSV)
    assert (first.imported, first.duplicates, str(first)) == (5, 0, "october.csv")
    assert account.transactions.filter(counterparty="Grocer").count() == 2

    extended = CSV + b"2026-11-05,-20.00,Bookshop,,\n"
    second = services.import_file(account, "november.csv", extended)
    assert (second.imported, second.duplicates) == (1, 5)
    assert account.transactions.count() == 6
    newest = account.transactions.first()
    assert newest is not None
    assert str(newest) == "2026-11-05 -20.00 Bookshop"
    assert (str(account), str(Category(name="Food"))) == ("Everyday", "Food")


def test_same_file_in_two_accounts_is_not_a_duplicate(user: User, account: BankAccount) -> None:
    other = BankAccount.objects.create(user=user, name="Savings", iban=OTHER_IBAN)
    services.import_file(account, "a.csv", CSV)
    assert services.import_file(other, "a.csv", CSV).imported == 5


# Summary


def test_summary_totals_by_category_and_month(imported: BankAccount, user: User) -> None:
    result = services.summary(user, *BOTH)
    assert (result.income, result.expenses, result.net) == (
        Decimal("2500.00"),
        Decimal("904.30"),
        Decimal("1595.70"),
    )
    assert result.by_category == [("Housing", Decimal("800.00")), ("Uncategorised", Decimal("104.30"))]
    assert result.by_month == [
        (dt.date(2026, 10, 1), Decimal("2500.00"), Decimal("891.80")),
        (dt.date(2026, 11, 1), Decimal(0), Decimal("12.50")),
    ]


def test_summary_text(imported: BankAccount, user: User, other_user: User) -> None:
    assert services.summary_text(user, *BOTH) == (
        "Finances 2026-10-01..2026-11-30 (EUR)\n"
        "income 2500.00, expenses 904.30, net +1595.70\n"
        "expenses by category: Housing 800.00, Uncategorised 104.30\n"
        "month, income, expenses\n"
        "2026-10 2500.00 891.80\n"
        "2026-11 0.00 12.50"
    )
    assert services.summary_text(other_user, *BOTH) == "No transactions from 2026-10-01 to 2026-11-30."


def test_transactions_text(imported: BankAccount, user: User, monkeypatch: pytest.MonkeyPatch) -> None:
    assert services.transactions_text(user, *OCTOBER).splitlines()[:3] == [
        "date, amount EUR, counterparty, category, message",
        "2026-10-15 -800.00 Landlord [Housing] Rent October",
        "2026-10-03 -45.90 Grocer [-]",
    ]
    assert services.transactions_text(user, *BOTH, "housing").count("\n") == 1
    assert services.transactions_text(user, *BOTH, "lunch").endswith("Cafe [-] Lunch")
    assert services.transactions_text(user, *OCTOBER, "yacht") == (
        "No transactions from 2026-10-01 to 2026-10-31 matching 'yacht'."
    )
    assert services.transactions_text(user, dt.date(2025, 1, 1), dt.date(2025, 1, 2)) == (
        "No transactions from 2025-01-01 to 2025-01-02."
    )
    monkeypatch.setattr(services, "MAX_TEXT_ROWS", 2)
    lines = services.transactions_text(user, *BOTH).splitlines()
    assert len(lines) == 4
    assert lines[-1].startswith("(only the newest 2 shown")


# REST API


def test_finance_api_requires_login(api_client: APIClient) -> None:
    for path in ("accounts", "categories", "transactions", "summary"):
        assert api_client.get(f"/api/finance/{path}/").status_code == 403


def test_accounts_are_created_with_normalised_ibans(user_client: APIClient) -> None:
    created = user_client.post(
        "/api/finance/accounts/", {"name": "Everyday", "iban": "fi21 1234 5600 0007 85"}, format="json"
    )
    assert created.status_code == 201
    assert created.json() == {
        "id": created.json()["id"],
        "name": "Everyday",
        "iban": IBAN,
        "bank": "generic",
        "currency": "EUR",
    }
    duplicate = user_client.post("/api/finance/accounts/", {"name": "Again", "iban": IBAN}, format="json")
    assert (duplicate.status_code, list(duplicate.json())) == (400, ["iban"])
    invalid = user_client.post("/api/finance/accounts/", {"name": "Bad", "iban": "FI00"}, format="json")
    assert (invalid.status_code, list(invalid.json())) == (400, ["iban"])
    missing = user_client.post("/api/finance/accounts/", {"name": "None"}, format="json")
    assert missing.status_code == 400
    renamed = user_client.patch(
        f"/api/finance/accounts/{created.json()['id']}/", {"name": "Daily", "iban": IBAN}, format="json"
    )
    assert (renamed.status_code, renamed.json()["name"]) == (200, "Daily")


def test_file_upload_imports_and_reports(user_client: APIClient, account: BankAccount) -> None:
    status, body = upload(user_client, account, CSV)
    assert (status, body["imported"], body["duplicates"], body["filename"]) == (201, 5, 0, "export.csv")
    assert upload(user_client, account, CSV)[1]["duplicates"] == 5
    assert upload(user_client, account, b"nonsense") == (
        400,
        {"file": "The file needs a header row with at least the columns date and amount."},
    )
    assert (
        user_client.post(f"/api/finance/accounts/{account.pk}/import/", {}, format="multipart").status_code
        == 400
    )


def test_oversized_upload_is_refused(
    user_client: APIClient, account: BankAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(services, "MAX_FILE_BYTES", 10)
    assert upload(user_client, account, CSV) == (400, {"file": "The file is too large."})
    assert not Transaction.objects.exists()


def test_transactions_can_be_listed_filtered_and_categorised(
    user_client: APIClient, imported: BankAccount, other_user: User
) -> None:
    everything = user_client.get("/api/finance/transactions/").json()
    assert [item["date"] for item in everything][:2] == ["2026-11-02", "2026-10-15"]
    assert everything[0]["amount"] == "-12.50"

    def count(**params: str | int) -> int:
        return len(user_client.get("/api/finance/transactions/", params).json())

    assert count(start="2026-10-02", end="2026-10-31") == 3
    assert count(search="rent") == 1
    assert count(uncategorised=True) == 4
    assert count(account=imported.pk) == 5

    food = user_client.post("/api/finance/categories/", {"name": "Food"}, format="json").json()
    assert user_client.post("/api/finance/categories/", {"name": "Food"}, format="json").status_code == 400
    grocery = next(item for item in everything if item["counterparty"] == "Grocer")
    url = f"/api/finance/transactions/{grocery['id']}/"
    changed = user_client.patch(url, {"category": food["id"], "amount": "1.00"}, format="json")
    assert (changed.status_code, changed.json()["category"], changed.json()["amount"]) == (
        200,
        food["id"],
        "-45.90",
    )
    assert count(category=food["id"]) == 1
    assert user_client.patch(url, {"category": None}, format="json").json()["category"] is None

    foreign = Category.objects.create(user=other_user, name="Theirs")
    assert user_client.patch(url, {"category": foreign.pk}, format="json").status_code == 400
    assert user_client.delete(url).status_code == 405
    assert user_client.put(url, {"category": food["id"]}, format="json").status_code == 405


def test_summary_api(user_client: APIClient, other_client: APIClient, imported: BankAccount) -> None:
    period = {"start": "2026-10-01", "end": "2026-11-30"}
    body = user_client.get("/api/finance/summary/", period).json()
    assert (body["income"], body["expenses"], body["net"]) == ("2500.00", "904.30", "1595.70")
    assert body["by_category"][0] == {"category": "Housing", "total": "800.00"}
    assert body["by_month"][1] == {"month": "2026-11-01", "income": "0.00", "expenses": "12.50"}
    assert other_client.get("/api/finance/summary/", period).json()["by_month"] == []
    assert user_client.get("/api/finance/summary/").status_code == 400
    assert (
        user_client.get("/api/finance/summary/", {"start": "2026-11-30", "end": "2026-10-01"}).status_code
        == 400
    )


def test_finance_data_is_hidden_from_other_users(imported: BankAccount, other_client: APIClient) -> None:
    assert_hidden_from(other_client, "/api/finance/accounts/", imported.pk)
    assert_hidden_from(other_client, "/api/finance/categories/", Category.objects.get().pk)
    assert other_client.get("/api/finance/transactions/").json() == []
    transaction = Transaction.objects.first()
    assert transaction is not None
    assert (
        other_client.patch(
            f"/api/finance/transactions/{transaction.pk}/", {"category": None}, format="json"
        ).status_code
        == 404
    )
    assert upload(other_client, imported, CSV)[0] == 404


# MCP


@pytest.mark.django_db(transaction=True)
def test_finance_tools(server: TestClient, user: User) -> None:
    account = BankAccount.objects.create(user=user, name="Everyday", iban=IBAN)
    services.import_file(account, "october.csv", CSV)
    outsider = AgentToken.objects.create_token(user, "sleep agent", {"sleep": "read"})[1]
    assert not {"finance_summary", "transactions"} & tool_names(server, outsider)

    token = AgentToken.objects.create_token(user, "finance agent", {"finance": "read"})[1]
    period = {"start": "2026-10-01", "end": "2026-10-31"}
    assert text(call(server, token, "finance_summary", period)).startswith(
        "Finances 2026-10-01..2026-10-31 (EUR)"
    )
    assert "Landlord" in text(call(server, token, "transactions", {**period, "search": "rent"}))
    assert text(call(server, token, "transactions")).startswith(("No transactions", "date, amount"))
    assert (
        text(call(server, token, "finance_summary", {"start": "October"})) == "Invalid date. Use YYYY-MM-DD."
    )
    backwards = {"start": "2026-10-31", "end": "2026-10-01"}
    assert text(call(server, token, "transactions", backwards)) == "The start must not be after the end."
