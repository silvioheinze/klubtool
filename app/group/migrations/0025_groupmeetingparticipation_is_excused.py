from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0024_add_membership_period'),
    ]

    operations = [
        migrations.AddField(
            model_name='groupmeetingparticipation',
            name='is_excused',
            field=models.BooleanField(default=False, help_text='Whether the member is excused from the meeting'),
        ),
    ]
