
from decimal import Decimal
from django.conf import settings
from django.db import models

from accounting.models import Account, JournalEntry
from common.models import TenantScopedModel
from parties.models import Party


class PurchaseBillStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    POSTED = "POSTED", "Posted"
    CANCELLED = "CANCELLED", "Cancelled"


class PurchaseBill(TenantScopedModel):
    bill_number = models.CharField(max_length=30, blank=True)

    party = models.ForeignKey(
        Party, on_delete=models.PROTECT, related_name="purchase_bills",
        help_text="Must be a Vendor or Both -- enforced by the serializer's queryset, not here.",
    )

    bill_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=PurchaseBillStatus.choices, default=PurchaseBillStatus.DRAFT)
    narration = models.TextField(blank=True)

    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))

    payable_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, null=True, blank=True,
        related_name="purchase_bills_as_payable",
        help_text="Accounts Payable control account credited when this bill is posted.",
    )
    tax_receivable_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, null=True, blank=True,
        related_name="purchase_bills_as_tax_receivable",
        help_text="Asset account (input tax/VAT receivable) debited for tax_amount. Required only if tax_amount > 0.",
    )

    journal_entry = models.OneToOneField(
        JournalEntry, on_delete=models.PROTECT, null=True, blank=True, related_name="purchase_bill",
    )

    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="posted_purchase_bills",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="created_purchase_bills",
    )

    class Meta:
        db_table = "purchase_bills"
        ordering = ["-bill_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "bill_number"], name="unique_bill_number_per_org"),
        ]

    def __str__(self):
        return f"{self.bill_number} - {self.party.name}"

    @property
    def subtotal(self) -> Decimal:
        return sum((line.amount for line in self.lines.all()), Decimal("0.00"))

    @property
    def total_amount(self) -> Decimal:
        return self.subtotal + self.tax_amount


class PurchaseBillLine(TenantScopedModel):
    purchase_bill = models.ForeignKey(PurchaseBill, on_delete=models.CASCADE, related_name="lines")

    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("1.00"))
    rate = models.DecimalField(max_digits=18, decimal_places=2)

    expense_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, null=True, blank=True, related_name="purchase_bill_lines",
        help_text="Expense account this line is debited to. Required by the time the bill is posted.",
    )

    order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "purchase_bill_lines"
        ordering = ["order", "created_at"]

    def __str__(self):
        return f"{self.description} ({self.quantity} x {self.rate})"

    @property
    def amount(self) -> Decimal:
        return (self.quantity * self.rate).quantize(Decimal("0.01"))