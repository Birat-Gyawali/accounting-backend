from django.core.exceptions import ValidationError
from django.db import models
from decimal import Decimal
from django.conf import settings
from django.db.models import Sum

from common.models import TenantScopedModel


class AccountType(models.TextChoices):
    ASSET = "ASSET", "Asset"
    LIABILITY = "LIABILITY", "Liability"
    EQUITY = "EQUITY", "Equity"
    INCOME = "INCOME", "Income"
    EXPENSE = "EXPENSE", "Expense"


def validate_account_hierarchy(account) -> None:

    if account.parent_id is None:
        return

    if account.parent_id == account.id:
        raise ValidationError({"parent": "An account cannot be its own parent."})

    if account.parent.organization_id != account.organization_id:
        raise ValidationError({"parent": "Parent account must belong to the same organization."})

    seen = {account.id}
    current = account.parent
    for _ in range(50):  # bounded: a data bug elsewhere shouldn't hang this
        if current is None:
            break
        if current.id in seen:
            raise ValidationError({"parent": "This would create a circular account hierarchy."})
        seen.add(current.id)
        current = current.parent


class Account(TenantScopedModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, help_text="Short account code, e.g. '1000'.")
    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    description = models.TextField(blank=True)

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,  # block deleting an account that still has children
        related_name="children",
        help_text="Optional parent account, for grouping (e.g. 'Cash' under 'Current Assets').",
    )


    is_system = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "accounts"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "code"], name="unique_account_code_per_org"),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        super().clean()
        validate_account_hierarchy(self)

class JournalEntryStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    POSTED = "POSTED", "Posted"


def validate_line_amounts(debit: Decimal, credit: Decimal) -> None:

    if debit < 0 or credit < 0:
        raise ValidationError("Amounts cannot be negative.")
    if debit > 0 and credit > 0:
        raise ValidationError("A line cannot have both a debit and a credit amount.")
    if debit == 0 and credit == 0:
        raise ValidationError("A line must have a nonzero debit or credit amount.")


class JournalEntry(TenantScopedModel):

    entry_date = models.DateField()
    reference_number = models.CharField(max_length=50, blank=True)
    narration = models.TextField(help_text="Why this entry exists -- required for every entry, posted or not.")
    status = models.CharField(max_length=10, choices=JournalEntryStatus.choices, default=JournalEntryStatus.DRAFT)

    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.PROTECT, related_name="posted_journal_entries",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.PROTECT, related_name="created_journal_entries",
    )

    class Meta:
        db_table = "journal_entries"
        ordering = ["-entry_date", "-created_at"]

    def __str__(self):
        return f"{self.entry_date} - {self.narration[:40]}"

    @property
    def total_debit(self) -> Decimal:
        return self.lines.aggregate(total=Sum("debit_amount"))["total"] or Decimal("0.00")

    @property
    def total_credit(self) -> Decimal:
        return self.lines.aggregate(total=Sum("credit_amount"))["total"] or Decimal("0.00")

    @property
    def is_balanced(self) -> bool:
        return self.total_debit == self.total_credit


class JournalEntryLine(TenantScopedModel):

    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="journal_lines")
    description = models.CharField(max_length=255, blank=True)

    debit_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    credit_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))

    order = models.PositiveIntegerField(default=0)  # server-assigned, not client-settable

    class Meta:
        db_table = "journal_entry_lines"
        ordering = ["order", "created_at"]

    def __str__(self):
        return f"{self.account.code} Dr:{self.debit_amount} Cr:{self.credit_amount}"

    def clean(self):
        super().clean()
        validate_line_amounts(self.debit_amount, self.credit_amount)
        if self.account_id and self.journal_entry_id and self.account.organization_id != self.organization_id:
            raise ValidationError({"account": "Account must belong to the same organization as the journal entry."})