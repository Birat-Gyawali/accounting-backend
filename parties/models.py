from django.db import models

from common.models import TenantScopedModel


class PartyType(models.TextChoices):
    CUSTOMER = "CUSTOMER", "Customer"
    VENDOR = "VENDOR", "Vendor"
    BOTH = "BOTH", "Both"


class Party(TenantScopedModel):
    name = models.CharField(max_length=255)
    party_type = models.CharField(max_length=10, choices=PartyType.choices, default=PartyType.CUSTOMER)

    phone = models.CharField(
        max_length=20, blank=True,
        help_text="e.g. +977-98XXXXXXXX. Kept as text: leading zeros and the country code matter.",
    )
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=500, blank=True)

    pan_number = models.CharField(
        "PAN number", max_length=20, blank=True,
        help_text="Permanent Account Number issued by Nepal's Inland Revenue Department.",
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "parties"
        ordering = ["name"]
        verbose_name_plural = "parties"

    def __str__(self):
        return f"{self.name} ({self.get_party_type_display()})"

    @property
    def is_customer(self) -> bool:
        return self.party_type in (PartyType.CUSTOMER, PartyType.BOTH)

    @property
    def is_vendor(self) -> bool:
        return self.party_type in (PartyType.VENDOR, PartyType.BOTH)