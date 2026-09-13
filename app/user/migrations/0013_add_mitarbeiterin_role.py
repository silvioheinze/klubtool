# Add Mitarbeiterin role for group membership

from django.db import migrations


def add_mitarbeiterin_role(apps, schema_editor):
    """Add Mitarbeiterin role for group membership."""
    Role = apps.get_model('user', 'Role')
    Role.objects.get_or_create(
        name='Mitarbeiterin',
        defaults={
            'description': 'Staff member of the group with basic participation rights',
            'is_active': True,
            'permissions': {'permissions': ['group.view']},
        },
    )


def reverse_add_mitarbeiterin_role(apps, schema_editor):
    Role = apps.get_model('user', 'Role')
    Role.objects.filter(name='Mitarbeiterin').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0012_add_mcp_token'),
    ]

    operations = [
        migrations.RunPython(add_mitarbeiterin_role, reverse_add_mitarbeiterin_role),
    ]
