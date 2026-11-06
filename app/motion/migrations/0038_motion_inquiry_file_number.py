from django.db import migrations, models
from django.utils.translation import gettext_lazy as _


class Migration(migrations.Migration):

    dependencies = [
        ('motion', '0037_filefield_max_length_500'),
    ]

    operations = [
        migrations.AddField(
            model_name='motion',
            name='file_number',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Official file / case number (optional)',
                max_length=100,
                verbose_name=_('Aktenzahl'),
            ),
        ),
        migrations.AddField(
            model_name='inquiry',
            name='file_number',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Official file / case number (optional)',
                max_length=100,
                verbose_name=_('Aktenzahl'),
            ),
        ),
    ]
