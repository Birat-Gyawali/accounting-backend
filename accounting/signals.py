from django.db.models.signals import post_save
from django.dispatch import receiver
from organizations.models import Organization
from accounting.services.account_setup import create_default_accounts


@receiver(post_save, sender=Organization)
def create_default_accounts_on_org_creation(sender, instance, created, **kwargs):
    if created:
        create_default_accounts(instance)