# Generated manually: add status to CommitteeMeeting, remove from Committee

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('local', '0036_committee_status'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='committee',
            name='status',
        ),
        migrations.AddField(
            model_name='committeemeeting',
            name='status',
            field=models.CharField(
                choices=[
                    ('scheduled', 'Scheduled'),
                    ('completed', 'Completed'),
                    ('cancelled', 'Cancelled'),
                    ('invited', 'Invited'),
                ],
                default='scheduled',
                help_text='Current status of the meeting',
                max_length=20,
            ),
        ),
    ]
