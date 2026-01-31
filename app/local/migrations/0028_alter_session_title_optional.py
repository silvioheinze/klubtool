# Generated manually: Session title optional, set on create to council name + date

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('local', '0027_committeemeetingattachment'),
    ]

    operations = [
        migrations.AlterField(
            model_name='session',
            name='title',
            field=models.CharField(
                blank=True,
                default='',
                help_text="Title of the session (set automatically on create: council name + date)",
                max_length=200,
            ),
        ),
    ]
