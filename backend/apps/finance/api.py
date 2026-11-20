"""REST API for personal finances."""

from django.db.models import QuerySet
from django_filters import rest_framework as filters
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer, ValidationError
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.finance import services
from apps.finance.importers import ImportError_
from apps.finance.models import BankAccount, Category, Transaction
from apps.finance.serializers import (
    BankAccountSerializer,
    CategorySerializer,
    FinanceSummarySerializer,
    ImportBatchSerializer,
    ImportUploadSerializer,
    PeriodSerializer,
    TransactionSerializer,
)


def _user(request: Request) -> User:
    user = request.user
    assert isinstance(user, User)  # noqa: S101 - guaranteed by IsAuthenticated
    return user


class CategoryViewSet(viewsets.ModelViewSet[Category]):
    """The signed-in user's transaction categories."""

    serializer_class = CategorySerializer
    queryset = Category.objects.none()

    def get_queryset(self) -> QuerySet[Category]:
        """Return only the categories of the signed-in user."""
        return Category.objects.for_user(_user(self.request))

    def perform_create(self, serializer: BaseSerializer[Category]) -> None:
        """Create the category for the signed-in user."""
        serializer.save(user=self.request.user)


class BankAccountViewSet(viewsets.ModelViewSet[BankAccount]):
    """The signed-in user's bank accounts."""

    serializer_class = BankAccountSerializer
    queryset = BankAccount.objects.none()

    def get_queryset(self) -> QuerySet[BankAccount]:
        """Return only the accounts of the signed-in user."""
        return BankAccount.objects.for_user(_user(self.request))

    def perform_create(self, serializer: BaseSerializer[BankAccount]) -> None:
        """Create the account for the signed-in user."""
        serializer.save(user=self.request.user)

    @extend_schema(request=ImportUploadSerializer, responses={201: ImportBatchSerializer})
    @action(detail=True, methods=["post"], url_path="import", parser_classes=[MultiPartParser])
    def import_file(self, request: Request, pk: str | None = None) -> Response:
        """Import a transaction file exported from the bank. Entries imported before are skipped."""
        upload = ImportUploadSerializer(data=request.data)
        upload.is_valid(raise_exception=True)
        file = upload.validated_data["file"]
        if file.size > services.MAX_FILE_BYTES:
            raise ValidationError({"file": "The file is too large."})
        try:
            batch = services.import_file(self.get_object(), file.name, file.read())
        except ImportError_ as error:
            raise ValidationError({"file": str(error)}) from error
        return Response(ImportBatchSerializer(batch).data, status=status.HTTP_201_CREATED)


class TransactionFilter(filters.FilterSet):
    """Filter transactions by account, category and dates."""

    start = filters.DateFilter(field_name="date", lookup_expr="gte")
    end = filters.DateFilter(field_name="date", lookup_expr="lte")
    uncategorised = filters.BooleanFilter(field_name="category", lookup_expr="isnull")

    class Meta:
        model = Transaction
        fields = ("account", "category")


class TransactionViewSet(
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet[Transaction],
):
    """The signed-in user's bank transactions, newest first. Only the category of one can be changed."""

    serializer_class = TransactionSerializer
    queryset = Transaction.objects.none()
    filterset_class = TransactionFilter
    http_method_names = ("get", "patch", "head", "options")

    def get_queryset(self) -> QuerySet[Transaction]:
        """Return only the transactions of the signed-in user, optionally matching ``search``."""
        return services.transactions_for(
            _user(self.request), search=self.request.query_params.get("search", "")
        )

    @extend_schema(parameters=[OpenApiParameter("search", OpenApiTypes.STR)])
    def list(self, request: Request, *args: object, **kwargs: object) -> Response:
        """List transactions. ``search`` matches the counterparty, message and category."""
        return super().list(request, *args, **kwargs)


class FinanceSummaryView(APIView):
    """Income and expenses of the signed-in user in a period."""

    @extend_schema(
        parameters=[
            OpenApiParameter("start", OpenApiTypes.DATE, required=True),
            OpenApiParameter("end", OpenApiTypes.DATE, required=True),
        ],
        responses=FinanceSummarySerializer,
    )
    def get(self, request: Request) -> Response:
        """Return totals, expenses by category and totals by month."""
        period = PeriodSerializer(data=request.query_params)
        period.is_valid(raise_exception=True)
        result = services.summary(
            _user(request), period.validated_data["start"], period.validated_data["end"]
        )
        data = {
            "first": result.first,
            "last": result.last,
            "income": result.income,
            "expenses": result.expenses,
            "net": result.net,
            "by_category": [{"category": name, "total": total} for name, total in result.by_category],
            "by_month": [
                {"month": month, "income": income, "expenses": expenses}
                for month, income, expenses in result.by_month
            ],
        }
        return Response(FinanceSummarySerializer(data).data)
