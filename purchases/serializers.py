from decimal import Decimal
from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from accounting.models import Account, AccountType
from common.numbering import allocate_next_number
from parties.models import Party, PartyType
from .models import PurchaseBill, PurchaseBillLine, PurchaseBillStatus


class PurchaseBillLineSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)

    class Meta:
        model = PurchaseBillLine
        fields = ["id", "description", "quantity", "rate", "amount", "expense_account"]
        read_only_fields = ["id", "amount"]

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value

    def validate_rate(self, value):
        if value < 0:
            raise serializers.ValidationError("Rate cannot be negative.")
        return value


class PurchaseBillSerializer(serializers.ModelSerializer):
    lines = PurchaseBillLineSerializer(many=True)
    subtotal = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    party_name = serializers.CharField(source="party.name", read_only=True)
    journal_entry_id = serializers.UUIDField(read_only=True)
    created_by_email = serializers.SerializerMethodField()
    posted_by_email = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseBill
        fields = [
            "id", "bill_number", "party", "party_name",
            "bill_date", "due_date", "status", "narration",
            "tax_amount", "payable_account", "tax_receivable_account",
            "lines", "subtotal", "total_amount",
            "journal_entry_id", "posted_at", "posted_by_email", "created_by_email",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status", "journal_entry_id", "posted_at",
            "posted_by_email", "created_by_email", "created_at", "updated_at",
        ]
        extra_kwargs = {"bill_number": {"required": False, "allow_blank": True}}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        organization_id = self.context.get("organization_id")
        if organization_id is None:
            return

        self.fields["party"].queryset = Party.objects.filter(
            organization_id=organization_id, is_active=True,
        ).filter(Q(party_type=PartyType.VENDOR) | Q(party_type=PartyType.BOTH))

        self.fields["payable_account"].queryset = Account.objects.filter(
            organization_id=organization_id, is_active=True, account_type=AccountType.LIABILITY,
        )
        self.fields["tax_receivable_account"].queryset = Account.objects.filter(
            organization_id=organization_id, is_active=True, account_type=AccountType.ASSET,
        )
        self.fields["lines"].child.fields["expense_account"].queryset = Account.objects.filter(
            organization_id=organization_id, is_active=True, account_type=AccountType.EXPENSE,
        )

    def get_created_by_email(self, obj):
        return obj.created_by.email if obj.created_by_id else None

    def get_posted_by_email(self, obj):
        return obj.posted_by.email if obj.posted_by_id else None

    def validate_bill_number(self, value):
        value = value.strip()
        if not value:
            return value

        organization_id = self.context.get("organization_id")
        existing = PurchaseBill.objects.filter(organization_id=organization_id, bill_number=value)
        if self.instance is not None:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError("A bill with this number already exists.")
        return value

    def validate(self, attrs):
        lines = attrs.get("lines")
        if lines is not None and len(lines) < 1:
            raise serializers.ValidationError({"lines": "A bill must have at least one line."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        lines_data = validated_data.pop("lines")
        organization_id = validated_data["organization_id"]

        if not validated_data.get("bill_number"):
            validated_data["bill_number"] = allocate_next_number(
                organization_id, key="purchase_bill", prefix="BILL",
            )

        bill = PurchaseBill.objects.create(**validated_data)
        self._save_lines(bill, organization_id, lines_data)
        return bill

    @transaction.atomic
    def update(self, instance, validated_data):
        lines_data = validated_data.pop("lines", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if lines_data is not None:
            instance.lines.all().delete()
            self._save_lines(instance, instance.organization_id, lines_data)
        return instance

    @staticmethod
    def _save_lines(bill, organization_id, lines_data):
        for index, line_data in enumerate(lines_data):
            PurchaseBillLine.objects.create(
                organization_id=organization_id, purchase_bill=bill, order=index, **line_data,
            )