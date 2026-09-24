from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounting.models import JournalEntry, JournalEntryLine, JournalEntryStatus
from .models import Payment, PaymentStatus, PaymentType


@transaction.atomic
def post_payment(payment: Payment, user) -> JournalEntry:
    """
        RECEIPT (money in):   Dr Cash/Bank            amount
                                   Cr Accounts Receivable  amount

        PAYMENT (money out):  Dr Accounts Payable      amount
                                   Cr Cash/Bank             amount
    """
    if payment.status != PaymentStatus.DRAFT:
        raise ValidationError("Only DRAFT payments/receipts can be posted.")

    if payment.cash_bank_account_id is None:
        raise ValidationError("A cash/bank account must be set before posting.")

    if payment.payment_type == PaymentType.RECEIPT:
        if payment.receivable_account_id is None:
            raise ValidationError("An Accounts Receivable account must be set before posting a receipt.")
        debit_account_id, debit_description = payment.cash_bank_account_id, f"Cash/Bank receipt - {payment.party.name}"
        credit_account_id, credit_description = payment.receivable_account_id, f"Accounts Receivable - {payment.party.name}"
    else:
        if payment.payable_account_id is None:
            raise ValidationError("An Accounts Payable account must be set before posting a payment.")
        debit_account_id, debit_description = payment.payable_account_id, f"Accounts Payable - {payment.party.name}"
        credit_account_id, credit_description = payment.cash_bank_account_id, f"Cash/Bank payment - {payment.party.name}"

    entry = JournalEntry.objects.create(
        organization_id=payment.organization_id,
        entry_date=payment.payment_date,
        reference_number=payment.payment_number,
        narration=f"{payment.get_payment_type_display()} {payment.payment_number} - {payment.party.name}",
        created_by=user,
    )

    JournalEntryLine.objects.create(
        organization_id=payment.organization_id, journal_entry=entry,
        account_id=debit_account_id, description=debit_description,
        debit_amount=payment.amount, credit_amount=0, order=0,
    )
    JournalEntryLine.objects.create(
        organization_id=payment.organization_id, journal_entry=entry,
        account_id=credit_account_id, description=credit_description,
        debit_amount=0, credit_amount=payment.amount, order=1,
    )

    if entry.total_debit != entry.total_credit:
        raise ValidationError("Generated journal entry is not balanced -- posting aborted.")

    now = timezone.now()
    entry.status = JournalEntryStatus.POSTED
    entry.posted_at = now
    entry.posted_by = user
    entry.save(update_fields=["status", "posted_at", "posted_by", "updated_at"])

    payment.journal_entry = entry
    payment.status = PaymentStatus.POSTED
    payment.posted_at = now
    payment.posted_by = user
    payment.save(update_fields=["journal_entry", "status", "posted_at", "posted_by", "updated_at"])

    return entry