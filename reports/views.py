from django.shortcuts import render
from datetime import date

from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from common.mixins import TenantScopedAPIViewMixin
from .services import build_trial_balance
from .services import build_profit_and_loss
from .services import build_balance_sheet

from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from common.mixins import TenantScopedAPIViewMixin
from .services import get_outstanding_receivables, get_outstanding_payables
from .serializers import OutstandingPartySerializer


def _parse_date(value: str | None, field_name: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValidationError({field_name: f"'{value}' is not a valid date -- expected YYYY-MM-DD."})


class TrialBalanceView(TenantScopedAPIViewMixin, APIView):
    def get(self, request):
        from_date = _parse_date(request.query_params.get("from_date"), "from_date")
        to_date = _parse_date(request.query_params.get("to_date"), "to_date")

        if from_date and to_date and from_date > to_date:
            raise ValidationError({"from_date": "from_date must be on or before to_date."})

        include_zero_balances = request.query_params.get("include_zero_balances", "").lower() == "true"

        data = build_trial_balance(
            self.get_organization_id(),
            from_date=from_date,
            to_date=to_date,
            include_zero_balances=include_zero_balances,
        )
        return Response(data)

class ProfitAndLossView(TenantScopedAPIViewMixin, APIView):
    """
    GET /api/reports/profit-loss/?from_date=YYYY-MM-DD&to_date=YYYY-MM-DD
    Only POSTED journal entries.
    """
    def get(self, request):
        from_date = _parse_date(request.query_params.get("from_date"), "from_date")
        to_date = _parse_date(request.query_params.get("to_date"), "to_date")
        if from_date and to_date and from_date > to_date:
            raise ValidationError({"from_date": "from_date must be on or before to_date."})
        data = build_profit_and_loss(self.get_organization_id(), from_date=from_date, to_date=to_date)
        return Response(data)


class BalanceSheetView(TenantScopedAPIViewMixin, APIView):
    """
    GET /api/reports/balance-sheet/?as_of_date=YYYY-MM-DD (defaults to today)
    """
    def get(self, request):
        as_of_date = _parse_date(request.query_params.get("as_of_date"), "as_of_date")
        data = build_balance_sheet(self.get_organization_id(), as_of_date=as_of_date)
        return Response(data)

class OutstandingReceivablesView(TenantScopedAPIViewMixin, GenericAPIView):
    serializer_class = OutstandingPartySerializer

    def get(self, request):
        organization_id = self.get_organization_id()
        data = get_outstanding_receivables(organization_id)
        serializer = self.get_serializer(data, many=True)
        return Response(serializer.data)


class OutstandingPayablesView(TenantScopedAPIViewMixin, GenericAPIView):
    serializer_class = OutstandingPartySerializer

    def get(self, request):
        organization_id = self.get_organization_id()
        data = get_outstanding_payables(organization_id)
        serializer = self.get_serializer(data, many=True)
        return Response(serializer.data)