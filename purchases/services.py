
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounting.models import JournalEntry, JournalEntryLine, JournalEntryStatus
from .models import PurchaseBillStatus


@transaction.atomic
def post_purchase_bill(bill, user) -> JournalEntry:
    """
        Dr  <expense account A>           sum of that account's lines
        Dr  <expense account B>           ...
        Dr  Tax Receivable                 tax_amount   (only if > 0)
            Cr  Accounts Payable            total_amount
    """
    if bill.status != PurchaseBillStatus.DRAFT:
        raise ValidationError("Only DRAFT bills can be posted.")

    lines = list(bill.lines.select_related("expense_account").all())
    if not lines:
        raise ValidationError("Cannot post a bill with no line items.")
    if any(line.expense_account_id is None for line in lines):
        raise ValidationError("Every bill line must have an expense account set before posting.")
    if bill.payable_account_id is None:
        raise ValidationError("An Accounts Payable account must be set before posting.")
    if bill.tax_amount > 0 and bill.tax_receivable_account_id is None:
        raise ValidationError("A tax receivable account must be set before posting a bill with tax.")

    debits_by_account = {}
    for line in lines:
        debits_by_account[line.expense_account_id] = (
            debits_by_account.get(line.expense_account_id, Decimal("0.00")) + line.amount
        )

    subtotal = sum(debits_by_account.values(), Decimal("0.00"))
    total_amount = subtotal + bill.tax_amount
    if total_amount <= 0:
        raise ValidationError("Total bill amount must be greater than zero to post.")

    entry = JournalEntry.objects.create(
        organization_id=bill.organization_id,
        entry_date=bill.bill_date,
        reference_number=bill.bill_number,
        narration=f"Purchase Bill {bill.bill_number} - {bill.party.name}",
        created_by=user,
    )

    order = 0
    for account_id, amount in debits_by_account.items():
        if amount <= 0:
            continue
        JournalEntryLine.objects.create(
            organization_id=bill.organization_id, journal_entry=entry,
            account_id=account_id, description=f"Purchase expense - Bill {bill.bill_number}",
            debit_amount=amount, credit_amount=Decimal("0.00"), order=order,
        )
        order += 1

    if bill.tax_amount > 0:
        JournalEntryLine.objects.create(
            organization_id=bill.organization_id, journal_entry=entry,
            account_id=bill.tax_receivable_account_id,
            description=f"Tax receivable - Bill {bill.bill_number}",
            debit_amount=bill.tax_amount, credit_amount=Decimal("0.00"), order=order,
        )
        order += 1

    JournalEntryLine.objects.create(
        organization_id=bill.organization_id, journal_entry=entry,
        account_id=bill.payable_account_id, description=f"Accounts Payable - {bill.party.name}",
        debit_amount=Decimal("0.00"), credit_amount=total_amount, order=order,
    )

    if entry.total_debit != entry.total_credit:
        raise ValidationError("Generated journal entry is not balanced -- posting aborted.")

    now = timezone.now()
    entry.status = JournalEntryStatus.POSTED
    entry.posted_at = now
    entry.posted_by = user
    entry.save(update_fields=["status", "posted_at", "posted_by", "updated_at"])

    bill.journal_entry = entry
    bill.status = PurchaseBillStatus.POSTED
    bill.posted_at = now
    bill.posted_by = user
    bill.save(update_fields=["journal_entry", "status", "posted_at", "posted_by", "updated_at"])

    return entry