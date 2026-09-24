import uuid

from django.db import models

class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class TenantScopedModel(BaseModel):

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_set",
    )

    class Meta:
        abstract = True

class NumberSequence(TenantScopedModel):
    
    key = models.CharField(max_length=50, help_text="e.g. 'sales_invoice', 'purchase_bill'.")
    next_value = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "number_sequences"
        constraints = [
            models.UniqueConstraint(fields=["organization", "key"], name="unique_sequence_per_org_key"),
        ]
