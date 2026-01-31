# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0014_groupmeeting_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='groupmeeting',
            name='title',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Title (set automatically on create: Klubsitzung + date)',
                max_length=200,
            ),
        ),
    ]
