# Generated manually - update Django Site from SITE_DOMAIN and SITE_NAME settings

import os

from django.conf import settings
from django.db import migrations


def update_site_from_env(apps, schema_editor):
    """Update the Site model with domain and name from environment/settings."""
    Site = apps.get_model('sites', 'Site')
    site_id = getattr(settings, 'SITE_ID', 1)
    domain = getattr(settings, 'SITE_DOMAIN', None) or os.environ.get('SITE_DOMAIN', 'localhost')
    name = getattr(settings, 'SITE_NAME', None) or os.environ.get('SITE_NAME', 'Klubtool')
    Site.objects.update_or_create(
        id=site_id,
        defaults={'domain': domain, 'name': name},
    )


def reverse_update_site(apps, schema_editor):
    """Reverse: restore default example.com (no-op for forward-only data)."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0008_add_party_member_role'),
        ('sites', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(update_site_from_env, reverse_update_site),
    ]
