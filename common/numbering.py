
from django.db import IntegrityError, transaction
from .models import NumberSequence


def allocate_next_number(organization_id, key: str, prefix: str, padding: int = 6) -> str:

    try:
        with transaction.atomic():
            sequence, _ = NumberSequence.objects.select_for_update().get_or_create(
                organization_id=organization_id, key=key, defaults={"next_value": 1},
            )
    except IntegrityError:

        sequence = NumberSequence.objects.select_for_update().get(organization_id=organization_id, key=key)

    number = sequence.next_value
    sequence.next_value = number + 1
    sequence.save(update_fields=["next_value"])

    return f"{prefix}-{number:0{padding}d}"