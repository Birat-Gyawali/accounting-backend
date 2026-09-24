

import django.db.models.deletion
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0002_alter_account_options_account_description_and_more'),
        ('organizations', '0002_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='JournalEntry',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('entry_date', models.DateField()),
                ('reference_number', models.CharField(blank=True, max_length=50)),
                ('narration', models.TextField(help_text='Why this entry exists -- required for every entry, posted or not.')),
                ('status', models.CharField(choices=[('DRAFT', 'Draft'), ('POSTED', 'Posted')], default='DRAFT', max_length=10)),
                ('posted_at', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='created_journal_entries', to=settings.AUTH_USER_MODEL)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='%(app_label)s_%(class)s_set', to='organizations.organization')),
                ('posted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='posted_journal_entries', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'journal_entries',
                'ordering': ['-entry_date', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='JournalEntryLine',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('description', models.CharField(blank=True, max_length=255)),
                ('debit_amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=18)),
                ('credit_amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=18)),
                ('order', models.PositiveIntegerField(default=0)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='journal_lines', to='accounting.account')),
                ('journal_entry', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='accounting.journalentry')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='%(app_label)s_%(class)s_set', to='organizations.organization')),
            ],
            options={
                'db_table': 'journal_entry_lines',
                'ordering': ['order', 'created_at'],
            },
        ),
    ]
