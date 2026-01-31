# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0013_alter_groupmember_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='groupmeeting',
            name='status',
            field=models.CharField(
                choices=[('scheduled', 'Scheduled'), ('invited', 'Invited'), ('cancelled', 'Cancelled')],
                default='scheduled',
                help_text='Current status of the meeting',
                max_length=20,
            ),
        ),
    ]
