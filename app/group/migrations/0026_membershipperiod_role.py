from django.db import migrations, models

DATED_ROLE_PRIORITY = ['Leader', 'Deputy Leader', 'Member']


def backfill_period_roles(apps, schema_editor):
    MembershipPeriod = apps.get_model('group', 'MembershipPeriod')
    for period in MembershipPeriod.objects.select_related('member').iterator():
        role_names = set(period.member.roles.values_list('name', flat=True))
        chosen = 'Member'
        for name in DATED_ROLE_PRIORITY:
            if name in role_names:
                chosen = name
                break
        MembershipPeriod.objects.filter(pk=period.pk).update(role=chosen)


def remove_party_member_role(apps, schema_editor):
    Role = apps.get_model('user', 'Role')
    GroupMember = apps.get_model('group', 'GroupMember')
    party_roles = Role.objects.filter(name='Party member')
    if not party_roles.exists():
        return
    party_role = party_roles.first()
    for member in GroupMember.objects.filter(roles=party_role).iterator():
        member.roles.remove(party_role)
    party_role.delete()


def sync_dated_roles_from_periods(apps, schema_editor):
    GroupMember = apps.get_model('group', 'GroupMember')
    MembershipPeriod = apps.get_model('group', 'MembershipPeriod')
    Role = apps.get_model('user', 'Role')
    dated_names = DATED_ROLE_PRIORITY
    dated_roles = {name: Role.objects.get_or_create(
        name=name,
        defaults={'description': f'{name} role', 'is_active': True},
    )[0] for name in dated_names}
    for member in GroupMember.objects.iterator():
        for role in dated_roles.values():
            member.roles.remove(role)
        open_period = (
            MembershipPeriod.objects.filter(member=member, end_date__isnull=True)
            .order_by('-start_date', '-pk')
            .first()
        )
        if open_period and open_period.role in dated_roles:
            member.roles.add(dated_roles[open_period.role])


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0025_groupmeetingparticipation_is_excused'),
        ('user', '0013_add_mitarbeiterin_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='membershipperiod',
            name='role',
            field=models.CharField(
                choices=[('Leader', 'Leader'), ('Deputy Leader', 'Deputy Leader'), ('Member', 'Member')],
                default='Member',
                help_text='Role during this membership period',
                max_length=20,
            ),
        ),
        migrations.RunPython(backfill_period_roles, migrations.RunPython.noop),
        migrations.RunPython(remove_party_member_role, migrations.RunPython.noop),
        migrations.RunPython(sync_dated_roles_from_periods, migrations.RunPython.noop),
    ]
