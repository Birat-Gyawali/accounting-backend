from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from common.permissions import HasMinimumRole, draft_workflow_roles

from common.mixins import TenantScopedViewSetMixin
from .models import SalesInvoice, SalesInvoiceStatus
from .serializers import SalesInvoiceSerializer
from .services import post_sales_invoice


class SalesInvoiceViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = (
        SalesInvoice.objects.select_related(
            "party", "receivable_account", "tax_payable_account", "journal_entry", "created_by", "posted_by",
        ).prefetch_related("lines__income_account").all()
    )
    serializer_class = SalesInvoiceSerializer

    permission_classes = TenantScopedViewSetMixin.permission_classes + [HasMinimumRole]
    action_required_roles = draft_workflow_roles(post_actions=["post_invoice"], cancel_actions=["cancel_invoice"])

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
    "status": ["exact"],
    "party": ["exact"],
    "invoice_date": ["exact", "gte", "lte"],
    }
    search_fields = ["invoice_number", "narration"]
    ordering_fields = ["invoice_date", "created_at"]
    ordering = ["-invoice_date", "-created_at"]

    def perform_create(self, serializer):
        serializer.save(organization_id=self.get_organization_id(), created_by=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.status != SalesInvoiceStatus.DRAFT:
            raise PermissionDenied("Only DRAFT invoices can be edited.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status != SalesInvoiceStatus.DRAFT:
            raise PermissionDenied("Only DRAFT invoices can be deleted.")
        instance.delete()

    @action(detail=True, methods=["post"], url_path="post")
    def post_invoice(self, request, pk=None):
        invoice = self.get_object()
        post_sales_invoice(invoice, request.user)
        invoice.refresh_from_db()
        return Response(self.get_serializer(invoice).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel_invoice(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status != SalesInvoiceStatus.DRAFT:
            raise ValidationError("Only DRAFT invoices can be cancelled.")
        invoice.status = SalesInvoiceStatus.CANCELLED
        invoice.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(invoice).data)