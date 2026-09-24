from rest_framework import serializers

from .models import Party


class PartySerializer(serializers.ModelSerializer):
    is_customer = serializers.BooleanField(read_only=True)
    is_vendor = serializers.BooleanField(read_only=True)

    class Meta:
        model = Party
        fields = [
            "id", "name", "party_type", "phone", "email", "address",
            "pan_number", "is_active", "is_customer", "is_vendor", "created_at",
        ]
        read_only_fields = ["id", "created_at"]