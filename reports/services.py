from datetime import date
from decimal import Decimal
from django.utils import timezone
from accounting.models import AccountType
from decimal import Decimal
from itertools import groupby

from django.db.models import F, Sum, OuterRef, Subquery, DecimalField
from django.db.models.functions import Coalesce

from sales.models import SalesInvoice, SalesInvoiceLine
from purchases.models import PurchaseBill, PurchaseBillLine
from payments.models import Payment

from django.db.models import Sum

from accounting.models import JournalEntryLine, JournalEntryStatus


def _posted_lines(organization_id, from_date: date | None, to_date: date | None):

    qs = JournalEntryLine.objects.filter(
        organization_id=organization_id,
        journal_entry__status=JournalEntryStatus.POSTED,
    )
    if from_date is not None:
        qs = qs.filter(journal_entry__entry_date__gte=from_date)
    if to_date is not None:
        qs = qs.filter(journal_entry__entry_date__lte=to_date)
    return qs


def build_trial_balance(
    organization_id,
    from_date: date | None = None,
    to_date: date | None = None,
    include_zero_balances: bool = False,
) -> dict:
    aggregated = (
        _posted_lines(organization_id, from_date, to_date)
        .values("account_id", "account__code", "account__name", "account__account_type")
        .annotate(total_debit=Sum("debit_amount"), total_credit=Sum("credit_amount"))
    )

    rows_by_account_id = {row["account_id"]: row for row in aggregated}

    if include_zero_balances:
        from accounting.models import Account

        for account in Account.objects.filter(organization_id=organization_id, is_active=True).exclude(
            id__in=rows_by_account_id.keys()
        ):
            rows_by_account_id[account.id] = {
                "account_id": account.id,
                "account__code": account.code,
                "account__name": account.name,
                "account__account_type": account.account_type,
                "total_debit": Decimal("0.00"),
                "total_credit": Decimal("0.00"),
            }

    accounts = []
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")

    for row in sorted(rows_by_account_id.values(), key=lambda r: r["account__code"]):
        raw_debit = row["total_debit"] or Decimal("0.00")
        raw_credit = row["total_credit"] or Decimal("0.00")
        net = raw_debit - raw_credit
        if net > 0:
            debit, credit = net, Decimal("0.00")
        elif net < 0:
            debit, credit = Decimal("0.00"), -net
        else:
            debit, credit = Decimal("0.00"), Decimal("0.00")
        total_debit += debit
        total_credit += credit
        accounts.append({
            "account_id": row["account_id"],
            "code": row["account__code"],
            "name": row["account__name"],
            "account_type": row["account__account_type"],
            "total_debit": debit,
            "total_credit": credit,
        })

    return {
        "from_date": from_date,
        "to_date": to_date,
        "accounts": accounts,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "is_balanced": total_debit == total_credit,
    }

def _grouped_by_account(organization_id, from_date, to_date, account_types=None):
    """
    Shared by build_profit_and_loss and build_balance_sheet: group posted
    lines by account, optionally restricted to a set of account types,
    returning the raw (total_debit, total_credit) per account. Kept in
    one place so "how do we sum lines per account" can't quietly diverge
    between reports.
    """
    qs = _posted_lines(organization_id, from_date, to_date)
    if account_types is not None:
        qs = qs.filter(account__account_type__in=account_types)

    return (
        qs.values("account_id", "account__code", "account__name", "account__account_type")
        .annotate(total_debit=Sum("debit_amount"), total_credit=Sum("credit_amount"))
    )


def build_profit_and_loss(organization_id, from_date=None, to_date=None) -> dict:
    """
    Income accounts are naturally credit-heavy, Expense accounts are
    naturally debit-heavy -- so each account's reportable amount is
    "the side it naturally lives on minus the other side": credit-debit
    for Income, debit-credit for Expense.

    Only Net Profit/Loss is computed, not a separate Gross Profit.
    Gross Profit = Revenue - COGS needs a Cost-of-Goods-Sold distinction
    the Chart of Accounts doesn't have yet (one flat EXPENSE bucket).
    Smallest fix if you want it: an `is_cost_of_goods_sold` boolean on
    Account, splitting the expense total by it here.
    """
    rows = _grouped_by_account(
        organization_id, from_date, to_date, account_types=[AccountType.INCOME, AccountType.EXPENSE],
    )

    income_items, expense_items = [], []
    total_income = Decimal("0.00")
    total_expenses = Decimal("0.00")

    for row in sorted(rows, key=lambda r: r["account__code"]):
        debit = row["total_debit"] or Decimal("0.00")
        credit = row["total_credit"] or Decimal("0.00")
        item = {"account_id": row["account_id"], "code": row["account__code"], "name": row["account__name"]}

        if row["account__account_type"] == AccountType.INCOME:
            amount = credit - debit
            total_income += amount
            if amount != 0:
                income_items.append({**item, "amount": amount})
        else:
            amount = debit - credit
            total_expenses += amount
            if amount != 0:
                expense_items.append({**item, "amount": amount})

    return {
        "from_date": from_date,
        "to_date": to_date,
        "income": income_items,
        "total_income": total_income,
        "expenses": expense_items,
        "total_expenses": total_expenses,
        "net_profit": total_income - total_expenses,
    }


def build_balance_sheet(organization_id, as_of_date=None) -> dict:
    """
    A Balance Sheet is always "as of" a point in time, cumulative from
    inception -- no from_date here on purpose.

    THE PART THAT NEEDS EXPLAINING: this system has no period-end
    closing process (no step that transfers accumulated Income/Expense
    into an Equity "Retained Earnings" account at fiscal year-end). That
    means the current period's profit is sitting in Income/Expense
    accounts, NOT in Equity. If this only summed stored Equity accounts,
    Assets would NOT equal Liabilities + Equity -- it would be off by
    exactly the undistributed profit.

    So this computes net income from inception through as_of_date and
    folds it into Equity as an explicit synthetic line, "Retained
    Earnings (Current Period)" -- the standard approach any system takes
    without a formal closing entry.

    Why this guarantees the identity: every posted line, across ALL
    account types, sums to zero debit-minus-credit (the double-entry
    invariant enforced at posting time). Splitting that global sum by
    type and moving each type to its correct side of the equation
    algebraically rearranges into exactly
    Assets = Liabilities + Equity-accounts + Net-Income-to-date.
    It's arithmetic, not a check that might fail.
    """
    if as_of_date is None:
        as_of_date = timezone.localdate()

    rows = _grouped_by_account(
        organization_id, from_date=None, to_date=as_of_date,
        account_types=[AccountType.ASSET, AccountType.LIABILITY, AccountType.EQUITY,
                       AccountType.INCOME, AccountType.EXPENSE],
    )

    assets, liabilities, equity = [], [], []
    total_assets = total_liabilities = total_equity_accounts = Decimal("0.00")
    total_income = total_expenses = Decimal("0.00")

    for row in sorted(rows, key=lambda r: r["account__code"]):
        debit = row["total_debit"] or Decimal("0.00")
        credit = row["total_credit"] or Decimal("0.00")
        account_type = row["account__account_type"]
        item = {"account_id": row["account_id"], "code": row["account__code"], "name": row["account__name"]}

        if account_type == AccountType.ASSET:
            amount = debit - credit
            total_assets += amount
            if amount != 0:
                assets.append({**item, "amount": amount})
        elif account_type == AccountType.LIABILITY:
            amount = credit - debit
            total_liabilities += amount
            if amount != 0:
                liabilities.append({**item, "amount": amount})
        elif account_type == AccountType.EQUITY:
            amount = credit - debit
            total_equity_accounts += amount
            if amount != 0:
                equity.append({**item, "amount": amount})
        elif account_type == AccountType.INCOME:
            total_income += credit - debit
        elif account_type == AccountType.EXPENSE:
            total_expenses += debit - credit

    net_income_to_date = total_income - total_expenses
    if net_income_to_date != 0:
        equity.append({
            "account_id": None, "code": None,
            "name": "Retained Earnings (Current Period)", "amount": net_income_to_date,
        })
    total_equity = total_equity_accounts + net_income_to_date

    return {
        "as_of_date": as_of_date,
        "assets": assets, "total_assets": total_assets,
        "liabilities": liabilities, "total_liabilities": total_liabilities,
        "equity": equity, "total_equity": total_equity,
        "is_balanced": total_assets == (total_liabilities + total_equity),
    }

ZERO = Decimal("0.00")
MONEY_FIELD = DecimalField(max_digits=14, decimal_places=2)


def _money_subquery(qs):
    return Coalesce(Subquery(qs, output_field=MONEY_FIELD), ZERO, output_field=MONEY_FIELD)


def get_outstanding_receivables(organization_id):
    lines_sq = (
        SalesInvoiceLine.objects
        .filter(sales_invoice=OuterRef("pk"))
        .values("sales_invoice")
        .annotate(total=Sum(F("quantity") * F("rate"), output_field=MONEY_FIELD))
        .values("total")
    )
    paid_sq = (
        Payment.objects
        .filter(sales_invoice=OuterRef("pk"))
        .values("sales_invoice")
        .annotate(total=Sum("amount"))
        .values("total")
    )

    invoices = (
        SalesInvoice.objects
        .filter(organization_id=organization_id, status="POSTED")
        .annotate(
            lines_total=_money_subquery(lines_sq),
            paid_amount=_money_subquery(paid_sq),
        )
        .annotate(
            computed_total=F("lines_total") + F("tax_amount"),
            outstanding_amount=F("lines_total") + F("tax_amount") - F("paid_amount"),
        )
        .filter(outstanding_amount__gt=ZERO)
        .select_related("party")
        .order_by("party__name", "id")
    )
    return _group_by_party(invoices, number_field="invoice_number")


def get_outstanding_payables(organization_id):
    lines_sq = (
        PurchaseBillLine.objects
        .filter(purchase_bill=OuterRef("pk"))
        .values("purchase_bill")
        .annotate(total=Sum(F("quantity") * F("rate"), output_field=MONEY_FIELD))
        .values("total")
    )
    paid_sq = (
        Payment.objects
        .filter(purchase_bill=OuterRef("pk"))
        .values("purchase_bill")
        .annotate(total=Sum("amount"))
        .values("total")
    )

    bills = (
        PurchaseBill.objects
        .filter(organization_id=organization_id, status="POSTED")
        .annotate(
            lines_total=_money_subquery(lines_sq),
            paid_amount=_money_subquery(paid_sq),
        )
        .annotate(
            computed_total=F("lines_total") + F("tax_amount"),
            outstanding_amount=F("lines_total") + F("tax_amount") - F("paid_amount"),
        )
        .filter(outstanding_amount__gt=ZERO)
        .select_related("party")
        .order_by("party__name", "id")
    )
    return _group_by_party(bills, number_field="bill_number")


def _group_by_party(annotated_qs, number_field):
    """
    Groups an already party-ordered queryset into per-party summaries.
    groupby() only groups consecutive rows, hence order_by("party__name", ...) above.
    """
    rows = list(annotated_qs)
    result = []
    for party, group in groupby(rows, key=lambda r: r.party):
        group = list(group)
        total = sum((r.outstanding_amount for r in group), ZERO)
        result.append({
            "party_id": party.id,
            "party_name": party.name,
            "total_outstanding": total,
            "items": [
                {
                    "id": r.id,
                    "number": getattr(r, number_field),
                    "total_amount": r.computed_total,
                    "paid_amount": r.paid_amount,
                    "outstanding_amount": r.outstanding_amount,
                }
                for r in group
            ],
        })
    return result