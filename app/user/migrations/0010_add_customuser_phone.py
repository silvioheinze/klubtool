# Generated manually - add phone field to CustomUser

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0009_update_site_from_env'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='phone',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Contact telephone number (optional)',
                max_length=30,
                verbose_name='Phone',
            ),
        ),
    ]
