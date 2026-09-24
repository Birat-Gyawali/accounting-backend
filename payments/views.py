from django.shortcuts import render
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from common.permissions import HasMinimumRole, draft_workflow_roles

from common.mixins import TenantScopedViewSetMixin
from .models import Payment, PaymentStatus
from .serializers import PaymentSerializer
from .services import post_payment


class PaymentViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Payment.objects.select_related(
        "party", "sales_invoice", "purchase_bill",
        "cash_bank_account", "receivable_account", "payable_account",
        "journal_entry", "created_by", "posted_by",
    ).all()
    serializer_class = PaymentSerializer

    permission_classes = TenantScopedViewSetMixin.permission_classes + [HasMinimumRole]
    action_required_roles = draft_workflow_roles(post_actions=["post_payment_action"])

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
    "payment_type": ["exact"], "status": ["exact"], "party": ["exact"],
    "payment_date": ["exact", "gte", "lte"],
    }
    search_fields = ["payment_number", "reference_number", "notes"]
    ordering_fields = ["payment_date", "created_at"]
    ordering = ["-payment_date", "-created_at"]

    def perform_create(self, serializer):
        serializer.save(organization_id=self.get_organization_id(), created_by=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.status != PaymentStatus.DRAFT:
            raise PermissionDenied("Only DRAFT payments/receipts can be edited.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status != PaymentStatus.DRAFT:
            raise PermissionDenied("Only DRAFT payments/receipts can be deleted.")
        instance.delete()

    @action(detail=True, methods=["post"], url_path="post")
    def post_payment_action(self, request, pk=None):
        payment = self.get_object()
        post_payment(payment, request.user)
        payment.refresh_from_db()
        return Response(self.get_serializer(payment).data)