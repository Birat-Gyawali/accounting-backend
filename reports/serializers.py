from rest_framework import serializers


class OutstandingItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    number = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    paid_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    outstanding_amount = serializers.DecimalField(max_digits=14, decimal_places=2)


class OutstandingPartySerializer(serializers.Serializer):
    party_id = serializers.UUIDField()
    party_name = serializers.CharField()
    total_outstanding = serializers.DecimalField(max_digits=14, decimal_places=2)
    items = OutstandingItemSerializer(many=True)