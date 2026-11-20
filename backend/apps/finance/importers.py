"""Readers for the transaction exports of banks.

Each bank exports its own CSV dialect, so each gets its own importer, chosen
by the ``bank`` of the account that a file is imported into.

PLACEHOLDER for bank formats. Importers for real banks (OP, Nordea, S-Pankki
and so on) will be written against example files. Until then only the
``generic`` format below exists; it lets files be prepared by hand, and keeps
the import pipeline (duplicate detection, batches, categories) working and
tested. To add a bank, write a function like :func:`read_generic` and register
it in :data:`IMPORTERS`.
"""

import csv
import datetime as dt
import io
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class Row:
    """One transaction as read from a file. Money leaving the account is negative."""

    date: dt.date
    amount: Decimal
    counterparty: str = ""
    message: str = ""
    reference: str = ""


class ImportError_(ValueError):  # noqa: N801, N818 - "ImportError" is a builtin
    """Raised when a file is not in the format that the importer expects."""


def read_generic(text: str) -> list[Row]:
    """Read Nexus's own simple CSV format.

    A header row with the columns ``date`` (YYYY-MM-DD) and ``amount`` (a dot
    as the decimal separator, negative for money leaving the account), and
    optionally ``counterparty``, ``message`` and ``reference``. Comma-separated.
    """
    reader = csv.DictReader(io.StringIO(text))
    if not {"date", "amount"} <= set(reader.fieldnames or ()):
        msg = "The file needs a header row with at least the columns date and amount."
        raise ImportError_(msg)
    rows: list[Row] = []
    for number, record in enumerate(reader, start=2):
        try:
            rows.append(
                Row(
                    date=dt.date.fromisoformat((record["date"] or "").strip()),
                    amount=Decimal((record["amount"] or "").strip()),
                    counterparty=(record.get("counterparty") or "").strip(),
                    message=(record.get("message") or "").strip(),
                    reference=(record.get("reference") or "").strip(),
                ),
            )
        except (ValueError, InvalidOperation) as error:
            msg = f"Line {number}: the date or the amount could not be read."
            raise ImportError_(msg) from error
    return rows


#: Importers by the key stored in ``BankAccount.bank``, with the name shown to users.
IMPORTERS: dict[str, tuple[str, Callable[[str], list[Row]]]] = {
    "generic": ("Generic CSV (date, amount, counterparty, message, reference)", read_generic),
}
