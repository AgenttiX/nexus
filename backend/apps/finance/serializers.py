"""Serializers for personal finances."""

from rest_framework import serializers

from apps.finance.models import BankAccount, Category, ImportBatch, Transaction


class OwnedNameSerializer[M: (Category, BankAccount)](serializers.ModelSerializer[M]):
    """Reports a clash with another of the user's objects as a field error rather than a database error."""

    unique_field = "name"

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        """Check that the user has no other object with the same value in ``unique_field``."""
        model = self.Meta.model  # type: ignore[attr-defined]
        others = model.objects.for_user(self.context["request"].user)
        if self.instance is not None:
            others = others.exclude(pk=self.instance.pk)
        value = attrs.get(self.unique_field)
        if value is not None and others.filter(**{self.unique_field: value}).exists():
            raise serializers.ValidationError({self.unique_field: "You already have one with this value."})
        return attrs


class CategorySerializer(OwnedNameSerializer[Category]):
    """A category of transactions."""

    class Meta:
        model = Category
        fields = ("id", "name")


class BankAccountSerializer(OwnedNameSerializer[BankAccount]):
    """A bank account."""

    unique_field = "iban"

    class Meta:
        model = BankAccount
        fields = ("id", "name", "iban", "bank", "currency")

    def to_internal_value(self, data: dict[str, object]) -> dict[str, object]:
        """Accept IBANs as people write them, with spaces and in any case."""
        iban = data.get("iban")
        if isinstance(iban, str):
            data = {**data, "iban": iban.replace(" ", "").upper()}
        return super().to_internal_value(data)


class TransactionSerializer(serializers.ModelSerializer[Transaction]):
    """A bank transaction. Only its category can be changed."""

    class Meta:
        model = Transaction
        fields = ("id", "account", "date", "amount", "counterparty", "message", "reference", "category")
        read_only_fields = ("id", "account", "date", "amount", "counterparty", "message", "reference")

    def validate_category(self, value: Category | None) -> Category | None:
        """Allow only the user's own categories."""
        if value is not None and value.user != self.context["request"].user:
            msg = "Unknown category."
            raise serializers.ValidationError(msg)
        return value


class ImportBatchSerializer(serializers.ModelSerializer[ImportBatch]):
    """The result of importing a file."""

    class Meta:
        model = ImportBatch
        fields = ("id", "account", "filename", "created_at", "imported", "duplicates")


class ImportUploadSerializer(serializers.Serializer[object]):
    """A transaction file exported from an online bank."""

    file = serializers.FileField()


class PeriodSerializer(serializers.Serializer[dict[str, object]]):
    """The dates to include."""

    start = serializers.DateField()
    end = serializers.DateField()

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        """Require the start not to be after the end."""
        if attrs["start"] > attrs["end"]:  # type: ignore[operator]
            msg = "The start must not be after the end."
            raise serializers.ValidationError(msg)
        return attrs


class CategoryTotalSerializer(serializers.Serializer[object]):
    """Expenses of one category."""

    category = serializers.CharField()
    total = serializers.DecimalField(max_digits=14, decimal_places=2)


class MonthTotalSerializer(serializers.Serializer[object]):
    """Income and expenses of one month."""

    month = serializers.DateField()
    income = serializers.DecimalField(max_digits=14, decimal_places=2)
    expenses = serializers.DecimalField(max_digits=14, decimal_places=2)


class FinanceSummarySerializer(serializers.Serializer[object]):
    """Totals of a period. Expenses are positive numbers."""

    first = serializers.DateField()
    last = serializers.DateField()
    income = serializers.DecimalField(max_digits=14, decimal_places=2)
    expenses = serializers.DecimalField(max_digits=14, decimal_places=2)
    net = serializers.DecimalField(max_digits=14, decimal_places=2)
    by_category = CategoryTotalSerializer(many=True)
    by_month = MonthTotalSerializer(many=True)
