from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounting.models import JournalEntry, JournalEntryLine, JournalEntryStatus
from .models import SalesInvoiceStatus


@transaction.atomic
def post_sales_invoice(invoice, user) -> JournalEntry:
    """
        Dr  Accounts Receivable              total_amount
            Cr  <income account A>            sum of that account's lines
            Cr  <income account B>            ...
            Cr  Tax Payable                    tax_amount   (only if > 0)
    """
    if invoice.status != SalesInvoiceStatus.DRAFT:
        raise ValidationError("Only DRAFT invoices can be posted.")

    lines = list(invoice.lines.select_related("income_account").all())
    if not lines:
        raise ValidationError("Cannot post an invoice with no line items.")
    if any(line.income_account_id is None for line in lines):
        raise ValidationError("Every invoice line must have an income account set before posting.")
    if invoice.receivable_account_id is None:
        raise ValidationError("An Accounts Receivable account must be set before posting.")
    if invoice.tax_amount > 0 and invoice.tax_payable_account_id is None:
        raise ValidationError("A tax payable account must be set before posting an invoice with tax.")

    credits_by_account = {}
    for line in lines:
        credits_by_account[line.income_account_id] = (
            credits_by_account.get(line.income_account_id, Decimal("0.00")) + line.amount
        )

    subtotal = sum(credits_by_account.values(), Decimal("0.00"))
    total_amount = subtotal + invoice.tax_amount
    if total_amount <= 0:
        raise ValidationError("Total invoice amount must be greater than zero to post.")

    entry = JournalEntry.objects.create(
        organization_id=invoice.organization_id,
        entry_date=invoice.invoice_date,
        reference_number=invoice.invoice_number,
        narration=f"Sales Invoice {invoice.invoice_number} - {invoice.party.name}",
        created_by=user,
    )

    JournalEntryLine.objects.create(
        organization_id=invoice.organization_id, journal_entry=entry,
        account_id=invoice.receivable_account_id,
        description=f"Accounts Receivable - {invoice.party.name}",
        debit_amount=total_amount, credit_amount=Decimal("0.00"), order=0,
    )

    order = 1
    for account_id, amount in credits_by_account.items():
        if amount <= 0:
            continue
        JournalEntryLine.objects.create(
            organization_id=invoice.organization_id, journal_entry=entry,
            account_id=account_id, description=f"Sales income - Invoice {invoice.invoice_number}",
            debit_amount=Decimal("0.00"), credit_amount=amount, order=order,
        )
        order += 1

    if invoice.tax_amount > 0:
        JournalEntryLine.objects.create(
            organization_id=invoice.organization_id, journal_entry=entry,
            account_id=invoice.tax_payable_account_id,
            description=f"Tax payable - Invoice {invoice.invoice_number}",
            debit_amount=Decimal("0.00"), credit_amount=invoice.tax_amount, order=order,
        )

    if entry.total_debit != entry.total_credit:
        raise ValidationError("Generated journal entry is not balanced -- posting aborted.")

    now = timezone.now()
    entry.status = JournalEntryStatus.POSTED
    entry.posted_at = now
    entry.posted_by = user
    entry.save(update_fields=["status", "posted_at", "posted_by", "updated_at"])

    invoice.journal_entry = entry
    invoice.status = SalesInvoiceStatus.POSTED
    invoice.posted_at = now
    invoice.posted_by = user
    invoice.save(update_fields=["journal_entry", "status", "posted_at", "posted_by", "updated_at"])

    return entry