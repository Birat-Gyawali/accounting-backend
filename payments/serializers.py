from django.db import transaction
from rest_framework import serializers

from accounting.models import Account, AccountType
from common.numbering import allocate_next_number
from parties.models import Party
from purchases.models import PurchaseBill, PurchaseBillStatus
from sales.models import SalesInvoice, SalesInvoiceStatus
from .models import Payment, PaymentType

_NUMBERING_BY_TYPE = {
    PaymentType.RECEIPT: {"key": "receipt", "prefix": "RCPT"},
    PaymentType.PAYMENT: {"key": "payment", "prefix": "PMT"},
}


class PaymentSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source="party.name", read_only=True)
    journal_entry_id = serializers.UUIDField(read_only=True)
    created_by_email = serializers.SerializerMethodField()
    posted_by_email = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id", "payment_number", "payment_type", "party", "party_name",
            "payment_date", "amount", "payment_mode", "reference_number", "notes",
            "sales_invoice", "purchase_bill",
            "cash_bank_account", "receivable_account", "payable_account",
            "status", "journal_entry_id", "posted_at", "posted_by_email", "created_by_email",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status", "journal_entry_id", "posted_at",
            "posted_by_email", "created_by_email", "created_at", "updated_at",
        ]
        extra_kwargs = {"payment_number": {"required": False, "allow_blank": True}}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance is not None:
            self.fields["payment_type"].read_only = True

        organization_id = self.context.get("organization_id")
        if organization_id is None:
            return

        self.fields["party"].queryset = Party.objects.filter(organization_id=organization_id, is_active=True)
        self.fields["cash_bank_account"].queryset = Account.objects.filter(
            organization_id=organization_id, is_active=True, account_type=AccountType.ASSET,
        )
        self.fields["receivable_account"].queryset = Account.objects.filter(
            organization_id=organization_id, is_active=True, account_type=AccountType.ASSET,
        )
        self.fields["payable_account"].queryset = Account.objects.filter(
            organization_id=organization_id, is_active=True, account_type=AccountType.LIABILITY,
        )
        # Only POSTED invoices/bills are real obligations worth recording
        # a payment against.
        self.fields["sales_invoice"].queryset = SalesInvoice.objects.filter(
            organization_id=organization_id, status=SalesInvoiceStatus.POSTED,
        )
        self.fields["purchase_bill"].queryset = PurchaseBill.objects.filter(
            organization_id=organization_id, status=PurchaseBillStatus.POSTED,
        )

    def get_created_by_email(self, obj):
        return obj.created_by.email if obj.created_by_id else None

    def get_posted_by_email(self, obj):
        return obj.posted_by.email if obj.posted_by_id else None

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def validate_payment_number(self, value):
        value = value.strip()
        if not value:
            return value
        organization_id = self.context.get("organization_id")
        existing = Payment.objects.filter(organization_id=organization_id, payment_number=value)
        if self.instance is not None:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError("A payment with this number already exists.")
        return value

    def validate(self, attrs):

        payment_type = attrs.get("payment_type", getattr(self.instance, "payment_type", None))
        party = attrs.get("party", getattr(self.instance, "party", None))
        sales_invoice = attrs.get("sales_invoice", getattr(self.instance, "sales_invoice", None))
        purchase_bill = attrs.get("purchase_bill", getattr(self.instance, "purchase_bill", None))

        if payment_type == PaymentType.RECEIPT:
            if purchase_bill is not None:
                raise serializers.ValidationError({"purchase_bill": "A Receipt cannot link to a Purchase Bill."})
            if party is not None and not party.is_customer:
                raise serializers.ValidationError({"party": "A Receipt requires a Customer (or Both) party."})
            if sales_invoice is not None and party is not None and sales_invoice.party_id != party.id:
                raise serializers.ValidationError({"sales_invoice": "The linked invoice belongs to a different party."})

        elif payment_type == PaymentType.PAYMENT:
            if sales_invoice is not None:
                raise serializers.ValidationError({"sales_invoice": "A Payment cannot link to a Sales Invoice."})
            if party is not None and not party.is_vendor:
                raise serializers.ValidationError({"party": "A Payment requires a Vendor (or Both) party."})
            if purchase_bill is not None and party is not None and purchase_bill.party_id != party.id:
                raise serializers.ValidationError({"purchase_bill": "The linked bill belongs to a different party."})

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        organization_id = validated_data["organization_id"]
        if not validated_data.get("payment_number"):
            numbering = _NUMBERING_BY_TYPE[validated_data["payment_type"]]
            validated_data["payment_number"] = allocate_next_number(
                organization_id, key=numbering["key"], prefix=numbering["prefix"],
            )
        return Payment.objects.create(**validated_data)