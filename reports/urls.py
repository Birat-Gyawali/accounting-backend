from django.urls import path
from .views import (
    BalanceSheetView,
    ProfitAndLossView,
    TrialBalanceView,
    OutstandingReceivablesView,
    OutstandingPayablesView,
)

urlpatterns = [
    path("trial-balance/", TrialBalanceView.as_view(), name="trial-balance"),
    path("profit-loss/", ProfitAndLossView.as_view(), name="profit-loss"),
    path("balance-sheet/", BalanceSheetView.as_view(), name="balance-sheet"),
    path("outstanding-receivables/", OutstandingReceivablesView.as_view(), name="outstanding-receivables"),
    path("outstanding-payables/", OutstandingPayablesView.as_view(), name="outstanding-payables"),
]