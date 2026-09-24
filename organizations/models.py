"""
Organization = a tenant (one company using the software).
Membership   = which Users can access a given Organization, and with what role.

This is the join point of the multi-tenancy design: Organization <-many-to-
many-> User, through Membership, with `role` living on the join row (which
is exactly why this is a real model and not a bare ManyToManyField).
"""
from django.conf import settings
from django.db import models
from django.utils.text import slugify

from common.models import BaseModel


class Organization(BaseModel):

    name = models.CharField(max_length=255)
    slug = models.SlugField(
        max_length=255, unique=True, blank=True,
        help_text="Auto-generated from name if left blank. Used in URLs.",
    )

    pan_number = models.CharField("PAN number", max_length=20, blank=True)
    address = models.CharField(max_length=500, blank=True)

    currency = models.CharField(max_length=3, default="NPR")

    fiscal_year_start_month = models.PositiveSmallIntegerField(default=7)   # ~July
    fiscal_year_start_day = models.PositiveSmallIntegerField(default=17)

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "organizations"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            count = 1
            # Ensure unique slug if an organization with the same name exists
            while Organization.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{count}"
                count += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Role(models.TextChoices):

    STAFF = "STAFF", "Staff"
    MANAGER = "MANAGER", "Manager"
    ACCOUNTANT = "ACCOUNTANT", "Accountant"
    ADMIN = "ADMIN", "Admin"
    OWNER = "OWNER", "Owner"


class Membership(BaseModel):

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STAFF)

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "organization_memberships"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"], name="unique_membership_per_org_user",
            ),
        ]
        ordering = ["organization", "role"]

    def __str__(self):
        return f"{self.user.email} @ {self.organization.name} ({self.get_role_display()})"