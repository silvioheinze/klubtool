# Merge Group member role into Member role

from django.db import migrations


def merge_group_member_into_member(apps, schema_editor):
    """Reassign Group member to Member and remove the Group member role."""
    Role = apps.get_model('user', 'Role')
    GroupMember = apps.get_model('group', 'GroupMember')
    CustomUser = apps.get_model('user', 'CustomUser')

    member_role, _ = Role.objects.get_or_create(
        name='Member',
        defaults={
            'description': 'Regular group member with basic participation rights',
            'is_active': True,
            'permissions': {'permissions': ['group.view']},
        },
    )

    try:
        group_member_role = Role.objects.get(name='Group member')
    except Role.DoesNotExist:
        return

    for membership in GroupMember.objects.filter(roles=group_member_role):
        membership.roles.add(member_role)
        membership.roles.remove(group_member_role)

    CustomUser.objects.filter(role=group_member_role).update(role=member_role)

    group_member_role.delete()


def reverse_merge_group_member_into_member(apps, schema_editor):
    """Recreate Group member role (does not restore previous assignments)."""
    Role = apps.get_model('user', 'Role')
    Role.objects.get_or_create(
        name='Group member',
        defaults={
            'description': 'Group participant without party affiliation (basic group participation rights)',
            'is_active': True,
            'permissions': {'permissions': ['group.view']},
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0013_add_mitarbeiterin_role'),
        ('group', '0025_groupmeetingparticipation_is_excused'),
    ]

    operations = [
        migrations.RunPython(
            merge_group_member_into_member,
            reverse_merge_group_member_into_member,
        ),
    ]
