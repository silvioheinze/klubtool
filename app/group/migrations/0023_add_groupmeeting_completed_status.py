# Generated manually - add 'completed' status to GroupMeeting

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0022_groupevent_invited_members'),
    ]

    operations = [
        migrations.AlterField(
            model_name='groupmeeting',
            name='status',
            field=models.CharField(
                choices=[
                    ('scheduled', 'Scheduled'),
                    ('invited', 'Invited'),
                    ('completed', 'Completed'),
                    ('cancelled', 'Cancelled'),
                ],
                default='scheduled',
                help_text='Current status of the meeting',
                max_length=20,
            ),
        ),
    ]
