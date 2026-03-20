# Add Group member role for group membership (distinct from Member / Party member)

from django.db import migrations


def add_group_member_role(apps, schema_editor):
    """Add Group member role for group membership."""
    Role = apps.get_model('user', 'Role')
    Role.objects.get_or_create(
        name='Group member',
        defaults={
            'description': 'Group participant without party affiliation (basic group participation rights)',
            'is_active': True,
            'permissions': {'permissions': ['group.view']},
        },
    )


def reverse_add_group_member_role(apps, schema_editor):
    Role = apps.get_model('user', 'Role')
    Role.objects.filter(name='Group member').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0010_add_customuser_phone'),
    ]

    operations = [
        migrations.RunPython(add_group_member_role, reverse_add_group_member_role),
    ]
