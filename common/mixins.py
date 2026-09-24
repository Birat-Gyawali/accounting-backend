
from rest_framework.permissions import IsAuthenticated

from .permissions import IsTenantMember
from .tenancy import get_current_organization_id


class TenantScopedViewSetMixin:
    

    permission_classes = [IsAuthenticated, IsTenantMember]

    def get_organization_id(self):
        return get_current_organization_id(self.request)

    def get_queryset(self):
        organization_id = self.get_organization_id()
        return super().get_queryset().filter(organization_id=organization_id)

    def perform_create(self, serializer):
        serializer.save(organization_id=self.get_organization_id())

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["organization_id"] = self.get_organization_id()
        return context

class TenantScopedAPIViewMixin:
   
    permission_classes = [IsAuthenticated, IsTenantMember]

    def get_organization_id(self):
        return get_current_organization_id(self.request)