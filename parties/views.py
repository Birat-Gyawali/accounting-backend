from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.filters import OrderingFilter, SearchFilter

from common.mixins import TenantScopedViewSetMixin

from .models import Party
from .serializers import PartySerializer


class PartyViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):

    queryset = Party.objects.all()
    serializer_class = PartySerializer

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["party_type", "is_active"]
    search_fields = ["name", "phone", "pan_number"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]