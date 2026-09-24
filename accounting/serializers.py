from rest_framework import serializers
from decimal import Decimal
from django.db import transaction
from .models import JournalEntry, JournalEntryLine, JournalEntryStatus

from .models import Account


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = [
            "id", "name", "code", "account_type", "description",
            "parent", "is_system", "is_active", "created_at",
        ]
        read_only_fields = ["id", "is_system", "created_at"]


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        organization_id = self.context.get("organization_id")
        if organization_id is not None:

            self.fields["parent"].queryset = Account.objects.filter(organization_id=organization_id)

    def validate_parent(self, value):

        if value is None or self.instance is None:
            return value

        if value.pk == self.instance.pk:
            raise serializers.ValidationError("An account cannot be its own parent.")

        current = value
        seen = set()
        for _ in range(50):
            if current is None:
                break
            if current.pk == self.instance.pk:
                raise serializers.ValidationError("This would create a circular account hierarchy.")
            if current.pk in seen:
                break
            seen.add(current.pk)
            current = current.parent

        return value

class JournalEntryLineSerializer(serializers.ModelSerializer):
    

    class Meta:
        model = JournalEntryLine
        fields = ["id", "account", "description", "debit_amount", "credit_amount"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        debit = attrs.get("debit_amount") or Decimal("0.00")
        credit = attrs.get("credit_amount") or Decimal("0.00")
        if debit < 0 or credit < 0:
            raise serializers.ValidationError("Amounts cannot be negative.")
        if debit > 0 and credit > 0:
            raise serializers.ValidationError("A line cannot have both a debit and a credit amount.")
        if debit == 0 and credit == 0:
            raise serializers.ValidationError("A line must have a nonzero debit or credit amount.")
        return attrs


class JournalEntrySerializer(serializers.ModelSerializer):
    lines = JournalEntryLineSerializer(many=True)
    total_debit = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    total_credit = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    created_by_email = serializers.SerializerMethodField()
    posted_by_email = serializers.SerializerMethodField()

    class Meta:
        model = JournalEntry
        fields = [
            "id", "entry_date", "reference_number", "narration", "status",
            "lines", "total_debit", "total_credit",
            "posted_at", "posted_by_email", "created_by_email",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status", "posted_at", "posted_by_email", "created_by_email",
            "created_at", "updated_at",
        ]
        

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        organization_id = self.context.get("organization_id")
        if organization_id is not None:
            self.fields["lines"].child.fields["account"].queryset = Account.objects.filter(
                organization_id=organization_id, is_active=True,
            )

    def get_created_by_email(self, obj):
        return obj.created_by.email if obj.created_by_id else None

    def get_posted_by_email(self, obj):
        return obj.posted_by.email if obj.posted_by_id else None

    def validate(self, attrs):
        lines = attrs.get("lines")
        if lines is None:
            return attrs  # PATCH that doesn't touch lines

        if len(lines) < 2:
            raise serializers.ValidationError({"lines": "A journal entry must have at least 2 lines."})

        total_debit = sum((line["debit_amount"] for line in lines), Decimal("0.00"))
        total_credit = sum((line["credit_amount"] for line in lines), Decimal("0.00"))
        if total_debit != total_credit:
            raise serializers.ValidationError(
                {"lines": f"Total debit ({total_debit}) must equal total credit ({total_credit})."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        lines_data = validated_data.pop("lines")
        organization_id = validated_data["organization_id"]  # injected by TenantScopedViewSetMixin.perform_create
        entry = JournalEntry.objects.create(**validated_data)
        self._save_lines(entry, organization_id, lines_data)
        return entry

    @transaction.atomic
    def update(self, instance, validated_data):
        lines_data = validated_data.pop("lines", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if lines_data is not None:
            instance.lines.all().delete()  # full replace, not a merge/diff
            self._save_lines(instance, instance.organization_id, lines_data)
        return instance

    @staticmethod
    def _save_lines(entry, organization_id, lines_data):
        for index, line_data in enumerate(lines_data):
            JournalEntryLine.objects.create(
                organization_id=organization_id, journal_entry=entry, order=index, **line_data,
            )