from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from django.db.models import ProtectedError
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from .models import JournalEntry, JournalEntryStatus
from .serializers import JournalEntrySerializer
from common.permissions import HasMinimumRole, draft_workflow_roles

from common.mixins import TenantScopedViewSetMixin

from .models import Account
from .serializers import AccountSerializer


class AccountViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
   
    queryset = Account.objects.select_related("parent").all()
    serializer_class = AccountSerializer

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["account_type", "is_active", "parent"]
    search_fields = ["name", "code"]
    ordering_fields = ["code", "name", "account_type", "created_at"]
    ordering = ["code"]  

    def perform_update(self, serializer):
        if serializer.instance.is_system:
            raise PermissionDenied("System accounts cannot be modified.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.is_system:
            raise PermissionDenied("System accounts cannot be deleted.")
        instance.delete()
class JournalEntryViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = (
        JournalEntry.objects.select_related("created_by", "posted_by")
        .prefetch_related("lines__account")
        .all()
    )
    serializer_class = JournalEntrySerializer

    permission_classes = TenantScopedViewSetMixin.permission_classes + [HasMinimumRole]
    action_required_roles = draft_workflow_roles(post_actions=["post_entry"])

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {"status": ["exact"], "entry_date": ["exact", "gte", "lte"]}
    search_fields = ["narration", "reference_number"]
    ordering_fields = ["entry_date", "created_at"]
    ordering = ["-entry_date", "-created_at"]

    def perform_create(self, serializer):
        serializer.save(organization_id=self.get_organization_id(), created_by=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.status == JournalEntryStatus.POSTED:
            raise PermissionDenied(
                "Posted journal entries cannot be edited. Create an adjusting/reversing entry instead."
            )
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status == JournalEntryStatus.POSTED:
            raise PermissionDenied("Posted journal entries cannot be deleted.")
        instance.delete()

    @action(detail=True, methods=["post"], url_path="post")
    def post_entry(self, request, pk=None):
        entry = self.get_object()
        if entry.status == JournalEntryStatus.POSTED:
            raise ValidationError("This journal entry is already posted.")

        
        if entry.lines.count() < 2 or entry.total_debit != entry.total_credit:
            raise ValidationError("Cannot post an unbalanced or incomplete journal entry.")

        entry.status = JournalEntryStatus.POSTED
        entry.posted_at = timezone.now()
        entry.posted_by = request.user
        entry.save(update_fields=["status", "posted_at", "posted_by", "updated_at"])
        return Response(self.get_serializer(entry).data)
    
def perform_destroy(self, instance):
    if instance.is_system:
        raise PermissionDenied("System accounts cannot be deleted.")
    try:
        instance.delete()
    except ProtectedError:
        raise ValidationError(
            "This account cannot be deleted because other records "
            "(child accounts or journal entries) still reference it. "
            "Deactivate it instead by setting is_active=False."
        )