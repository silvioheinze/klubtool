# Generated manually: translate Session.status choice labels (gettext_lazy)

import django.utils.translation
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('district', '0045_committeemeeting_minutes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='session',
            name='status',
            field=models.CharField(
                choices=[
                    ('scheduled', django.utils.translation.gettext_lazy('Scheduled')),
                    ('in_progress', django.utils.translation.gettext_lazy('In Progress')),
                    ('completed', django.utils.translation.gettext_lazy('Completed')),
                    ('cancelled', django.utils.translation.gettext_lazy('Cancelled')),
                    ('invited', django.utils.translation.gettext_lazy('Invited')),
                ],
                default='scheduled',
                help_text='Current status of the session',
                max_length=20,
            ),
        ),
    ]