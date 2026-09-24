from django.contrib import admin

from .models import Party


@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ["name", "party_type", "phone", "pan_number", "is_active", "organization"]
    list_filter = ["party_type", "is_active"]
    search_fields = ["name", "phone", "pan_number", "email"]