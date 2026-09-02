# Allow CommitteeMeeting.history to be null so creates without auditlog (e.g. in tests) don't fail.
# Model keeps AuditlogHistoryField(); only the DB column is altered.

from django.db import migrations, models


def _committee_meeting_table(cursor):
    for table in ('local_committeemeeting', 'district_committeemeeting'):
        cursor.execute(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = %s)",
            [table],
        )
        if cursor.fetchone()[0]:
            return table
    return None


def allow_null_history(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        table = _committee_meeting_table(cursor)
        if table:
            cursor.execute(f'ALTER TABLE "{table}" ALTER COLUMN history DROP NOT NULL')


def disallow_null_history(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        table = _committee_meeting_table(cursor)
        if table:
            cursor.execute(f'ALTER TABLE "{table}" ALTER COLUMN history SET NOT NULL')


class Migration(migrations.Migration):

    dependencies = [
        ('district', '0021_committeemeeting'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(allow_null_history, disallow_null_history),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name='committeemeeting',
                    name='history',
                    field=models.JSONField(blank=True, default=dict, null=True),
                ),
            ],
        ),
    ]
