# Generated manually - add Party member role to group roles

from django.db import migrations


def add_party_member_role(apps, schema_editor):
    """Add Party member role for group membership."""
    Role = apps.get_model('user', 'Role')
    Role.objects.get_or_create(
        name='Party member',
        defaults={
            'description': 'Party member with basic group participation rights',
            'is_active': True,
            'permissions': {'permissions': ['group.view']},
        }
    )


def reverse_add_party_member_role(apps, schema_editor):
    """Remove Party member role."""
    Role = apps.get_model('user', 'Role')
    Role.objects.filter(name='Party member').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0007_add_calendar_subscription_token'),
    ]

    operations = [
        migrations.RunPython(add_party_member_role, reverse_add_party_member_role),
    ]
