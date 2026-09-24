from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError

from common.mixins import TenantScopedViewSetMixin
from common.permissions import HasMinimumRole

from .models import Membership, Role
from .serializers import MembershipSerializer, InviteSerializer, MembershipUpdateSerializer


class MembershipViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Membership.objects.select_related("user").all()
    serializer_class = MembershipSerializer

    permission_classes = TenantScopedViewSetMixin.permission_classes + [HasMinimumRole]
    action_required_roles = {
        "list": "STAFF",
        "retrieve": "STAFF",
        "invite": "ADMIN",
        "create": "ADMIN",
        "update": "ADMIN",
        "partial_update": "ADMIN",
        "destroy": "ADMIN",
        "deactivate": "ADMIN",
    }

    def get_serializer_class(self):
        if self.action in ["update", "partial_update"]:
            return MembershipUpdateSerializer
        if self.action == "invite":
            return InviteSerializer
        return MembershipSerializer

    def get_queryset(self):
        organization_id = self.get_organization_id()
        return super().get_queryset().filter(organization_id=organization_id)

    @action(detail=False, methods=["post"], url_path="invite")
    def invite(self, request):
        serializer = self.get_serializer(data=request.data, context={"organization_id": self.get_organization_id()})
        serializer.is_valid(raise_exception=True)
        membership = serializer.save()
        return Response(MembershipSerializer(membership).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        # Prevent changing own role
        if serializer.instance.user_id == self.request.user.id:
            raise PermissionDenied("You cannot change your own membership.")
        serializer.save()

    def perform_destroy(self, instance):
        # Prevent deleting own membership
        if instance.user_id == self.request.user.id:
            raise PermissionDenied("You cannot remove yourself from the organization.")
        # Prevent removing last OWNER
        if instance.role == Role.OWNER:
            other_owners = Membership.objects.filter(
                organization_id=instance.organization_id, role=Role.OWNER, is_active=True
            ).exclude(pk=instance.pk)
            if not other_owners.exists():
                raise ValidationError("Cannot remove the last OWNER of this organization.")
        instance.delete()

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        membership = self.get_object()
        if membership.user_id == request.user.id:
            raise PermissionDenied("You cannot deactivate yourself.")
        if membership.role == Role.OWNER:
            other_owners = Membership.objects.filter(
                organization_id=membership.organization_id, role=Role.OWNER, is_active=True
            ).exclude(pk=membership.pk)
            if not other_owners.exists():
                raise ValidationError("Cannot deactivate the last OWNER of this organization.")
        membership.is_active = False
        membership.save(update_fields=["is_active", "updated_at"])
        return Response(MembershipSerializer(membership).data)