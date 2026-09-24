import logging
from django.db import transaction
from accounting.constants import DEFAULT_SYSTEM_ACCOUNTS
from accounting.models import Account

logger = logging.getLogger(__name__)


@transaction.atomic
def create_default_accounts(organization):
    existing_codes = set(
        Account.objects.filter(organization=organization)
        .values_list("code", flat=True)
    )

    to_create = [
        Account(
            organization=organization,
            code=acct["code"],
            name=acct["name"],
            account_type=acct["account_type"],
            is_system=True,
        )
        for acct in DEFAULT_SYSTEM_ACCOUNTS
        if acct["code"] not in existing_codes
    ]

    if not to_create:
        return []

    created = Account.objects.bulk_create(to_create)
    logger.info("Created %d default accounts for organization %s.", len(created), organization.id)
    return created