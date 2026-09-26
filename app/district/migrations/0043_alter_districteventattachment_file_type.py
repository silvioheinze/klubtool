from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('district', '0042_districteventattachment'),
    ]

    operations = [
        migrations.AlterField(
            model_name='districteventattachment',
            name='file_type',
            field=models.CharField(
                choices=[
                    ('invitation', 'Invitation'),
                    ('agenda', 'Agenda'),
                    ('minutes', 'Minutes'),
                    ('other', 'Other'),
                ],
                default='other',
                max_length=20,
            ),
        ),
    ]
