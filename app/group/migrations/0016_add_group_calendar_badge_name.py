# Generated manually for Group.calendar_badge_name

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0015_alter_groupmeeting_title_optional'),
    ]

    operations = [
        migrations.AddField(
            model_name='group',
            name='calendar_badge_name',
            field=models.CharField(
                blank=True,
                help_text="Label shown for this group's meetings in the calendar list and monthly calendar (e.g. 'Group meeting'). Leave empty to use the default 'Group meeting'.",
                max_length=80,
            ),
        ),
    ]
