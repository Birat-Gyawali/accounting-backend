from django.shortcuts import render
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from common.permissions import HasMinimumRole, draft_workflow_roles

from common.mixins import TenantScopedViewSetMixin
from .models import PurchaseBill, PurchaseBillStatus
from .serializers import PurchaseBillSerializer
from .services import post_purchase_bill


class PurchaseBillViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = (
        PurchaseBill.objects.select_related(
            "party", "payable_account", "tax_receivable_account", "journal_entry", "created_by", "posted_by",
        ).prefetch_related("lines__expense_account").all()
    )
    serializer_class = PurchaseBillSerializer

    permission_classes = TenantScopedViewSetMixin.permission_classes + [HasMinimumRole]
    action_required_roles = draft_workflow_roles(post_actions=["post_bill"], cancel_actions=["cancel_bill"])

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {"status": ["exact"], "party": ["exact"], "bill_date": ["exact", "gte", "lte"]}
    search_fields = ["bill_number", "narration"]
    ordering_fields = ["bill_date", "created_at"]
    ordering = ["-bill_date", "-created_at"]

    def perform_create(self, serializer):
        serializer.save(organization_id=self.get_organization_id(), created_by=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.status != PurchaseBillStatus.DRAFT:
            raise PermissionDenied("Only DRAFT bills can be edited.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status != PurchaseBillStatus.DRAFT:
            raise PermissionDenied("Only DRAFT bills can be deleted.")
        instance.delete()

    @action(detail=True, methods=["post"], url_path="post")
    def post_bill(self, request, pk=None):
        bill = self.get_object()
        post_purchase_bill(bill, request.user)
        bill.refresh_from_db()
        return Response(self.get_serializer(bill).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel_bill(self, request, pk=None):
        bill = self.get_object()
        if bill.status != PurchaseBillStatus.DRAFT:
            raise ValidationError("Only DRAFT bills can be cancelled.")
        bill.status = PurchaseBillStatus.CANCELLED
        bill.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(bill).data)