# Generated manually for committee status

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('local', '0035_alter_sessionattachment_file_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='committee',
            name='status',
            field=models.CharField(
                choices=[
                    ('scheduled', 'Scheduled'),
                    ('completed', 'Completed'),
                    ('cancelled', 'Cancelled'),
                    ('invited', 'Invited'),
                ],
                default='scheduled',
                help_text='Current status of the committee',
                max_length=20,
            ),
        ),
    ]
