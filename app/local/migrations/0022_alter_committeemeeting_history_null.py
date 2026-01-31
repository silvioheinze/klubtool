# Allow CommitteeMeeting.history to be null so creates without auditlog (e.g. in tests) don't fail.
# Model keeps AuditlogHistoryField(); only the DB column is altered.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('local', '0021_committeemeeting'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE local_committeemeeting ALTER COLUMN history DROP NOT NULL;",
            reverse_sql="ALTER TABLE local_committeemeeting ALTER COLUMN history SET NOT NULL;",
            state_operations=[
                migrations.AlterField(
                    model_name='committeemeeting',
                    name='history',
                    field=models.JSONField(blank=True, default=dict, null=True),
                ),
            ],
        ),
    ]
