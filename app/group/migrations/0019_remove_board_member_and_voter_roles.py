# Generated manually - remove group roles "Board Member" and "Voter"

from django.db import migrations


def remove_roles(apps, schema_editor):
    """Remove Board Member and Voter roles from the user Role model."""
    Role = apps.get_model('user', 'Role')
    Role.objects.filter(name__in=['Board Member', 'Voter']).delete()


def reverse_remove_roles(apps, schema_editor):
    """Re-create Board Member and Voter roles (for migration rollback)."""
    Role = apps.get_model('user', 'Role')
    for name, description in [
        ('Board Member', 'Board member role for organizational governance'),
        ('Voter', 'Voter role'),
    ]:
        Role.objects.get_or_create(
            name=name,
            defaults={
                'description': description,
                'is_active': True,
                'permissions': {'permissions': []},
            }
        )


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0018_groupmeetingparticipation'),
        ('user', '0006_add_fixed_roles'),
    ]

    operations = [
        migrations.RunPython(remove_roles, reverse_remove_roles),
    ]
