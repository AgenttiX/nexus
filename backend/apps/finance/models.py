"""Bank accounts and their transactions."""

from typing import ClassVar

from django.core.exceptions import ValidationError
from django.db import models
from schwifty import IBAN
from schwifty.exceptions import SchwiftyException

from apps.core.models import OwnedManager, OwnedModel
from apps.finance.importers import IMPORTERS


def validate_iban(value: str) -> None:
    """Check that ``value`` is a valid IBAN in compact form (no spaces, upper case)."""
    try:
        compact = IBAN(value).compact
    except SchwiftyException as error:
        msg = "This is not a valid IBAN."
        raise ValidationError(msg) from error
    if compact != value:
        msg = "Write the IBAN without spaces and in upper case."
        raise ValidationError(msg)


class Category(OwnedModel):
    """A user's own class of transactions, such as groceries or rent."""

    name = models.CharField(max_length=100)

    objects: ClassVar[OwnedManager[Category]] = OwnedManager()

    class Meta(OwnedModel.Meta):
        ordering = ("name",)
        verbose_name_plural = "categories"
        constraints = (models.UniqueConstraint(fields=("user", "name"), name="unique_category_name"),)

    def __str__(self) -> str:
        """Return the category's name."""
        return self.name


class BankAccount(OwnedModel):
    """A bank account of a user."""

    name = models.CharField(max_length=100)
    iban = models.CharField(max_length=34, validators=[validate_iban], verbose_name="IBAN")
    bank = models.CharField(
        max_length=20,
        choices=[(key, label) for key, (label, _) in IMPORTERS.items()],
        default="generic",
        help_text="Decides the format in which transaction files are read.",
    )
    currency = models.CharField(max_length=3, default="EUR")

    objects: ClassVar[OwnedManager[BankAccount]] = OwnedManager()

    class Meta(OwnedModel.Meta):
        ordering = ("name",)
        constraints = (models.UniqueConstraint(fields=("user", "iban"), name="unique_account_iban"),)

    def __str__(self) -> str:
        """Return the account's name."""
        return self.name


class ImportBatch(models.Model):
    """One imported file, so that an import can be traced and undone as a whole."""

    account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name="imports")
    filename = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    imported = models.PositiveIntegerField(default=0)
    duplicates = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        """Return the name of the imported file."""
        return self.filename


class Transaction(models.Model):
    """One entry on a bank account. Money leaving the account is negative."""

    account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name="transactions")
    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="transactions")
    fingerprint = models.CharField(
        max_length=64, editable=False, help_text="Identifies the entry across imports."
    )
    date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    counterparty = models.CharField(max_length=300, blank=True)
    message = models.TextField(blank=True)
    reference = models.CharField(max_length=100, blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )

    class Meta:
        ordering = ("-date", "-id")
        indexes = (models.Index(fields=("account", "date")),)
        constraints = (models.UniqueConstraint(fields=("account", "fingerprint"), name="unique_transaction"),)

    def __str__(self) -> str:
        """Return the date, amount and counterparty of the entry."""
        return f"{self.date} {self.amount} {self.counterparty}".strip()
