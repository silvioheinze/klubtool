# Generated manually for invited members visibility

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0021_add_group_event'),
    ]

    operations = [
        migrations.AddField(
            model_name='groupevent',
            name='invited_members_only',
            field=models.BooleanField(
                default=False,
                help_text='When enabled, only selected members can see this event. Group managers and leaders always see it.',
            ),
        ),
        migrations.AddField(
            model_name='groupevent',
            name='invited_members',
            field=models.ManyToManyField(
                blank=True,
                help_text='Members who can see this event when visibility is restricted (managers/leaders always see it)',
                related_name='invited_to_events',
                to='group.groupmember',
            ),
        ),
    ]
