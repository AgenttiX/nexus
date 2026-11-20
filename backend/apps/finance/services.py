"""Importing and summarising bank transactions."""

import datetime as dt
import hashlib
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, QuerySet, Sum
from django.db.models.functions import TruncMonth

from apps.accounts.models import User
from apps.finance.importers import IMPORTERS, ImportError_, Row
from apps.finance.models import BankAccount, ImportBatch, Transaction

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TEXT_ROWS = 50
ZERO = Decimal(0)


def decode(data: bytes) -> str:
    """Decode a bank export, which is UTF-8 from most banks and Latin-1 from some."""
    if len(data) > MAX_FILE_BYTES:
        msg = "The file is too large."
        raise ImportError_(msg)
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def fingerprints(rows: list[Row]) -> list[str]:
    """Return an identifier for each row that stays the same when the row is imported again.

    Banks give no stable identifier, so it is a hash of the row's content.
    Identical rows of one file (two equal purchases on one day) are told apart
    by their order.
    """
    seen: Counter[tuple[object, ...]] = Counter()
    result: list[str] = []
    for row in rows:
        key = (row.date.isoformat(), str(row.amount), row.counterparty, row.message, row.reference)
        seen[key] += 1
        result.append(hashlib.sha256(repr((*key, seen[key])).encode()).hexdigest())
    return result


@transaction.atomic
def import_file(account: BankAccount, filename: str, data: bytes) -> ImportBatch:
    """Import a transaction file into ``account``, skipping entries that are already there."""
    _, read = IMPORTERS[account.bank]
    rows = read(decode(data))
    prints = fingerprints(rows)
    existing = set(account.transactions.filter(fingerprint__in=prints).values_list("fingerprint", flat=True))
    batch = ImportBatch.objects.create(account=account, filename=filename[:255])
    new = [
        Transaction(
            account=account,
            batch=batch,
            fingerprint=fingerprint,
            date=row.date,
            amount=row.amount,
            counterparty=row.counterparty[:300],
            message=row.message,
            reference=row.reference[:100],
        )
        for row, fingerprint in zip(rows, prints, strict=True)
        if fingerprint not in existing
    ]
    Transaction.objects.bulk_create(new)
    batch.imported = len(new)
    batch.duplicates = len(rows) - len(new)
    batch.save(update_fields=["imported", "duplicates"])
    return batch


def transactions_for(
    user: User,
    first: dt.date | None = None,
    last: dt.date | None = None,
    search: str = "",
) -> QuerySet[Transaction]:
    """Return the transactions of ``user``, newest first, optionally limited by dates and a search text."""
    result = Transaction.objects.filter(account__user=user).select_related("account", "category")
    if first:
        result = result.filter(date__gte=first)
    if last:
        result = result.filter(date__lte=last)
    if search:
        result = result.filter(
            Q(counterparty__icontains=search)
            | Q(message__icontains=search)
            | Q(category__name__icontains=search),
        )
    return result


@dataclass(frozen=True)
class Summary:
    """Totals of a period. Expenses are positive numbers."""

    first: dt.date
    last: dt.date
    income: Decimal
    expenses: Decimal
    by_category: list[tuple[str, Decimal]]
    by_month: list[tuple[dt.date, Decimal, Decimal]]

    @property
    def net(self) -> Decimal:
        """Income minus expenses."""
        return self.income - self.expenses


def summary(user: User, first: dt.date, last: dt.date) -> Summary:
    """Summarise the income and expenses of ``user`` between two dates, by category and by month."""
    rows = transactions_for(user, first, last)
    income_filter, expense_filter = Q(amount__gt=0), Q(amount__lt=0)
    totals = rows.aggregate(
        income=Sum("amount", filter=income_filter), expenses=Sum("amount", filter=expense_filter)
    )
    categories = (
        rows.filter(expense_filter).values("category__name").annotate(total=Sum("amount")).order_by("total")
    )
    months = (
        rows.annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(income=Sum("amount", filter=income_filter), expenses=Sum("amount", filter=expense_filter))
        .order_by("month")
    )
    return Summary(
        first=first,
        last=last,
        income=totals["income"] or ZERO,
        expenses=-(totals["expenses"] or ZERO),
        by_category=[(item["category__name"] or "Uncategorised", -item["total"]) for item in categories],
        by_month=[(item["month"], item["income"] or ZERO, -(item["expenses"] or ZERO)) for item in months],
    )


def summary_text(user: User, first: dt.date, last: dt.date) -> str:
    """Return the summary of a period as compact text for an AI agent."""
    result = summary(user, first, last)
    if not result.by_month:
        return f"No transactions from {first} to {last}."
    lines = [
        f"Finances {first}..{last} (EUR)",
        f"income {result.income:.2f}, expenses {result.expenses:.2f}, net {result.net:+.2f}",
        "expenses by category: " + ", ".join(f"{name} {total:.2f}" for name, total in result.by_category),
        "month, income, expenses",
    ]
    lines += [f"{month:%Y-%m} {income:.2f} {expenses:.2f}" for month, income, expenses in result.by_month]
    return "\n".join(lines)


def transactions_text(user: User, first: dt.date, last: dt.date, search: str = "") -> str:
    """Return the transactions of a period as compact text for an AI agent."""
    rows = list(transactions_for(user, first, last, search)[: MAX_TEXT_ROWS + 1])
    if not rows:
        return f"No transactions from {first} to {last}" + (f" matching {search!r}." if search else ".")
    lines = ["date, amount EUR, counterparty, category, message"]
    for row in rows[:MAX_TEXT_ROWS]:
        category = row.category.name if row.category else "-"
        lines.append(
            f"{row.date} {row.amount:+.2f} {row.counterparty or '-'} [{category}] {row.message}".rstrip()
        )
    if len(rows) > MAX_TEXT_ROWS:
        lines.append(f"(only the newest {MAX_TEXT_ROWS} shown; narrow the dates or add a search text)")
    return "\n".join(lines)
