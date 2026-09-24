from django.contrib import admin

from .models import Membership, Organization


class MembershipInline(admin.TabularInline):
    """Lets you add/edit an org's members directly from the Organization page."""
    model = Membership
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "pan_number", "currency", "is_active", "created_at"]
    list_filter = ["is_active", "currency"]
    search_fields = ["name", "slug", "pan_number"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [MembershipInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "organization", "role", "is_active", "created_at"]
    list_filter = ["role", "is_active"]
    autocomplete_fields = ["user", "organization"]
    search_fields = ["user__email", "organization__name"]