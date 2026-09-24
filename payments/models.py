from django.db import models
from decimal import Decimal
from django.conf import settings

from accounting.models import Account, JournalEntry
from common.models import TenantScopedModel
from parties.models import Party
from purchases.models import PurchaseBill
from sales.models import SalesInvoice


class PaymentType(models.TextChoices):
    RECEIPT = "RECEIPT", "Receipt"   # money in, from a customer
    PAYMENT = "PAYMENT", "Payment"   # money out, to a vendor


class PaymentMode(models.TextChoices):
    CASH = "CASH", "Cash"
    BANK_TRANSFER = "BANK_TRANSFER", "Bank Transfer"
    CHEQUE = "CHEQUE", "Cheque"
    MOBILE_WALLET = "MOBILE_WALLET", "Mobile Wallet"  # eSewa, Khalti, etc.
    OTHER = "OTHER", "Other"


class PaymentStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    POSTED = "POSTED", "Posted"


class Payment(TenantScopedModel):
    """
    Deliberately does NOT auto-derive receivable_account/payable_account
    from the linked sales_invoice/purchase_bill -- explicit beats
    implicit, same as Sales Invoice/Purchase Bill not having org-wide
    default accounts. The linked invoice/bill is for traceability;
    which account THIS payment hits is independently explicit.
    """

    payment_number = models.CharField(max_length=30, blank=True)
    payment_type = models.CharField(max_length=10, choices=PaymentType.choices)

    party = models.ForeignKey(
        Party, on_delete=models.PROTECT, related_name="payments",
        help_text="Customer (or Both) for a Receipt; Vendor (or Both) for a Payment.",
    )

    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    payment_mode = models.CharField(max_length=20, choices=PaymentMode.choices, default=PaymentMode.CASH)
    reference_number = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)

    sales_invoice = models.ForeignKey(
        SalesInvoice, on_delete=models.PROTECT, null=True, blank=True, related_name="receipts",
    )
    purchase_bill = models.ForeignKey(
        PurchaseBill, on_delete=models.PROTECT, null=True, blank=True, related_name="bill_payments",
    )

    cash_bank_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, null=True, blank=True, related_name="payments_as_cash_bank",
    )
    receivable_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, null=True, blank=True, related_name="receipts_as_receivable",
    )
    payable_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, null=True, blank=True, related_name="payments_as_payable",
    )

    journal_entry = models.OneToOneField(
        JournalEntry, on_delete=models.PROTECT, null=True, blank=True, related_name="payment",
    )

    status = models.CharField(max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.DRAFT)
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="posted_payments",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="created_payments",
    )

    class Meta:
        db_table = "payments"
        ordering = ["-payment_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "payment_number"], name="unique_payment_number_per_org"),
            
            models.CheckConstraint(condition=models.Q(amount__gt=Decimal("0.00")), name="payment_amount_positive"),
        ]

    def __str__(self):
        return f"{self.payment_number} ({self.get_payment_type_display()}) - {self.party.name}"
