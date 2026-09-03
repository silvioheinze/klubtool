# Generated manually for Local -> District rename

import django.db.models.deletion
from django.db import migrations, models


def _table_exists(cursor, name):
    cursor.execute(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = %s)",
        [name],
    )
    return cursor.fetchone()[0]


def rename_local_tables(apps, schema_editor):
    """Rename local_* tables to district_* when present (existing databases)."""
    renames = [
        ('local_local', 'district_district'),
        ('local_council', 'district_council'),
        ('local_committee', 'district_committee'),
        ('local_committeemeeting', 'district_committeemeeting'),
        ('local_committeemeetingattachment', 'district_committeemeetingattachment'),
        ('local_committeemember', 'district_committeemember'),
        ('local_committeeparticipationsubstitute', 'district_committeeparticipationsubstitute'),
        ('local_term', 'district_term'),
        ('local_party', 'district_party'),
        ('local_termseatdistribution', 'district_termseatdistribution'),
        ('local_session', 'district_session'),
        ('local_sessionattachment', 'district_sessionattachment'),
        ('local_sessionpresence', 'district_sessionpresence'),
        ('local_sessionexcuse', 'district_sessionexcuse'),
        ('local_localevent', 'district_districtevent'),
        ('local_localeventparticipation', 'district_districteventparticipation'),
    ]
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        for old_name, new_name in renames:
            if not _table_exists(cursor, old_name):
                continue
            if _table_exists(cursor, new_name):
                continue
            cursor.execute(f'ALTER TABLE "{old_name}" RENAME TO "{new_name}"')


def reverse_rename_local_tables(apps, schema_editor):
    renames = [
        ('district_district', 'local_local'),
        ('district_council', 'local_council'),
        ('district_committee', 'local_committee'),
        ('district_committeemeeting', 'local_committeemeeting'),
        ('district_committeemeetingattachment', 'local_committeemeetingattachment'),
        ('district_committeemember', 'local_committeemember'),
        ('district_committeeparticipationsubstitute', 'local_committeeparticipationsubstitute'),
        ('district_term', 'local_term'),
        ('district_party', 'local_party'),
        ('district_termseatdistribution', 'local_termseatdistribution'),
        ('district_session', 'local_session'),
        ('district_sessionattachment', 'local_sessionattachment'),
        ('district_sessionpresence', 'local_sessionpresence'),
        ('district_sessionexcuse', 'local_sessionexcuse'),
        ('district_districtevent', 'local_localevent'),
        ('district_districteventparticipation', 'local_localeventparticipation'),
    ]
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        for old_name, new_name in renames:
            if not _table_exists(cursor, old_name):
                continue
            if _table_exists(cursor, new_name):
                continue
            cursor.execute(f'ALTER TABLE "{old_name}" RENAME TO "{new_name}"')


def drop_old_constraints(apps, schema_editor):
    drops = [
        ('local_localeventparticipation', 'local_localeventparticipation_event_user_uniq'),
        ('district_localeventparticipation', 'local_localeventparticipation_event_user_uniq'),
        ('district_districteventparticipation', 'local_localeventparticipation_event_user_uniq'),
        ('local_committeeparticipationsubstitute', 'local_committeeparticipation_meeting_member_uniq'),
        ('district_committeeparticipationsubstitute', 'local_committeeparticipation_meeting_member_uniq'),
        ('local_committeeparticipationsubstitute', 'local_committeeparticipation_meeting_sub_uniq'),
        ('district_committeeparticipationsubstitute', 'local_committeeparticipation_meeting_sub_uniq'),
        ('local_sessionexcuse', 'local_sessionexcuse_session_user_uniq'),
        ('district_sessionexcuse', 'local_sessionexcuse_session_user_uniq'),
    ]
    with schema_editor.connection.cursor() as cursor:
        for table, constraint in drops:
            if _table_exists(cursor, table):
                cursor.execute(
                    f'ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "{constraint}"'
                )


def add_new_constraints(apps, schema_editor):
    adds = [
        (
            'district_districteventparticipation',
            'district_districteventparticipation_event_user_uniq',
            'UNIQUE (event_id, user_id)',
        ),
        (
            'district_committeeparticipationsubstitute',
            'district_committeeparticipation_meeting_member_uniq',
            'UNIQUE (committee_meeting_id, member_id)',
        ),
        (
            'district_committeeparticipationsubstitute',
            'district_committeeparticipation_meeting_sub_uniq',
            'UNIQUE (committee_meeting_id, substitute_member_id)',
        ),
        (
            'district_sessionexcuse',
            'district_sessionexcuse_session_user_uniq',
            'UNIQUE (session_id, user_id)',
        ),
    ]
    with schema_editor.connection.cursor() as cursor:
        for table, name, definition in adds:
            if not _table_exists(cursor, table):
                continue
            cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = %s)",
                [name],
            )
            if cursor.fetchone()[0]:
                continue
            cursor.execute(
                f'ALTER TABLE "{table}" ADD CONSTRAINT "{name}" {definition}'
            )


def reverse_add_new_constraints(apps, schema_editor):
    names = [
        'district_districteventparticipation_event_user_uniq',
        'district_committeeparticipation_meeting_member_uniq',
        'district_committeeparticipation_meeting_sub_uniq',
        'district_sessionexcuse_session_user_uniq',
    ]
    tables = [
        'district_districteventparticipation',
        'district_committeeparticipationsubstitute',
        'district_committeeparticipationsubstitute',
        'district_sessionexcuse',
    ]
    with schema_editor.connection.cursor() as cursor:
        for table, name in zip(tables, names):
            if _table_exists(cursor, table):
                cursor.execute(
                    f'ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "{name}"'
                )


class Migration(migrations.Migration):

    dependencies = [
        ('district', '0038_localevent_localeventparticipation'),
    ]

    operations = [
        migrations.RunPython(drop_old_constraints, migrations.RunPython.noop),
        migrations.RenameModel(
            old_name='Local',
            new_name='District',
        ),
        migrations.RenameModel(
            old_name='LocalEvent',
            new_name='DistrictEvent',
        ),
        migrations.RenameModel(
            old_name='LocalEventParticipation',
            new_name='DistrictEventParticipation',
        ),
        # Existing databases still have local_* table names. Rename those before
        # Django looks up district_council / district_party (RenameField).
        migrations.RunPython(rename_local_tables, reverse_rename_local_tables),
        # Clear explicit local_* db_table options so later operations use district_*.
        # Tables were already renamed in rename_local_tables.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelTable(name='district', table=None),
                migrations.AlterModelTable(name='districtevent', table=None),
                migrations.AlterModelTable(name='districteventparticipation', table=None),
            ],
            database_operations=[],
        ),
        migrations.RenameField(
            model_name='council',
            old_name='local',
            new_name='district',
        ),
        migrations.RenameField(
            model_name='party',
            old_name='local',
            new_name='district',
        ),
        migrations.RenameField(
            model_name='districtevent',
            old_name='local',
            new_name='district',
        ),
        migrations.AlterField(
            model_name='party',
            name='district',
            field=models.ForeignKey(
                blank=True,
                help_text='District this party belongs to',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='parties',
                to='district.district',
            ),
        ),
        migrations.AlterField(
            model_name='districtevent',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                help_text='User who created the event',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='created_district_events',
                to='user.customuser',
            ),
        ),
        migrations.AlterField(
            model_name='districteventparticipation',
            name='user',
            field=models.ForeignKey(
                help_text='User',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='district_event_participations',
                to='user.customuser',
            ),
        ),
        migrations.RunPython(add_new_constraints, reverse_add_new_constraints),
        migrations.AlterModelOptions(
            name='district',
            options={'ordering': ['name'], 'verbose_name': 'District', 'verbose_name_plural': 'Districts'},
        ),
        migrations.RunSQL(
            sql="UPDATE django_content_type SET app_label = 'district' WHERE app_label = 'local';",
            reverse_sql="UPDATE django_content_type SET app_label = 'local' WHERE app_label = 'district';",
        ),
    ]
