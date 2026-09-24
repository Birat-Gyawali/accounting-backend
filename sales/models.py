
from decimal import Decimal
from django.conf import settings
from django.db import models

from accounting.models import Account, JournalEntry
from common.models import TenantScopedModel
from parties.models import Party


class SalesInvoiceStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    POSTED = "POSTED", "Posted"
    CANCELLED = "CANCELLED", "Cancelled"


class SalesInvoice(TenantScopedModel):
    invoice_number = models.CharField(max_length=30, blank=True)

    party = models.ForeignKey(
        Party, on_delete=models.PROTECT, related_name="sales_invoices",
        help_text="Must be a Customer or Both -- enforced by the serializer's queryset, not here.",
    )

    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=SalesInvoiceStatus.choices, default=SalesInvoiceStatus.DRAFT)
    narration = models.TextField(blank=True)

    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))

    receivable_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, null=True, blank=True,
        related_name="sales_invoices_as_receivable",
        help_text="Accounts Receivable control account debited when this invoice is posted.",
    )
    tax_payable_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, null=True, blank=True,
        related_name="sales_invoices_as_tax_payable",
        help_text="Liability account credited for tax_amount when posted. Required only if tax_amount > 0.",
    )

    journal_entry = models.OneToOneField(
        JournalEntry, on_delete=models.PROTECT, null=True, blank=True, related_name="sales_invoice",
    )

    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="posted_sales_invoices",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="created_sales_invoices",
    )

    class Meta:
        db_table = "sales_invoices"
        ordering = ["-invoice_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "invoice_number"], name="unique_invoice_number_per_org"),
        ]

    def __str__(self):
        return f"{self.invoice_number} - {self.party.name}"

    @property
    def subtotal(self) -> Decimal:
        return sum((line.amount for line in self.lines.all()), Decimal("0.00"))

    @property
    def total_amount(self) -> Decimal:
        return self.subtotal + self.tax_amount


class SalesInvoiceLine(TenantScopedModel):
    sales_invoice = models.ForeignKey(SalesInvoice, on_delete=models.CASCADE, related_name="lines")

    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("1.00"))
    rate = models.DecimalField(max_digits=18, decimal_places=2)

    income_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, null=True, blank=True, related_name="sales_invoice_lines",
        help_text="Income account this line's revenue is credited to. Required by the time the invoice is posted.",
    )

    order = models.PositiveIntegerField(default=0)  # server-assigned

    class Meta:
        db_table = "sales_invoice_lines"
        ordering = ["order", "created_at"]

    def __str__(self):
        return f"{self.description} ({self.quantity} x {self.rate})"

    @property
    def amount(self) -> Decimal:
        return (self.quantity * self.rate).quantize(Decimal("0.01"))