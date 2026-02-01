# Generated manually for Council.calendar_badge_name

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('local', '0029_alter_session_title'),
    ]

    operations = [
        migrations.AddField(
            model_name='council',
            name='calendar_badge_name',
            field=models.CharField(
                blank=True,
                help_text="Label shown for this council's sessions in the calendar list and monthly calendar (e.g. 'City Council'). Leave empty to use the default 'Council'.",
                max_length=80,
            ),
        ),
    ]
