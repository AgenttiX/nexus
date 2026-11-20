"""URLs of the finance app."""

from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.finance.api import BankAccountViewSet, CategoryViewSet, FinanceSummaryView, TransactionViewSet

router = SimpleRouter()
router.register("finance/accounts", BankAccountViewSet, basename="bank-account")
router.register("finance/categories", CategoryViewSet, basename="category")
router.register("finance/transactions", TransactionViewSet, basename="transaction")

urlpatterns = [
    path("finance/summary/", FinanceSummaryView.as_view(), name="finance-summary"),
    *router.urls,
]
