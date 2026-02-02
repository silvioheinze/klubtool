# Generated manually for GroupMeetingParticipation

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0017_minuteitem'),
    ]

    operations = [
        migrations.CreateModel(
            name='GroupMeetingParticipation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_present', models.BooleanField(default=True, help_text='Whether the member is present at the meeting')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('meeting', models.ForeignKey(help_text='Group meeting', on_delete=django.db.models.deletion.CASCADE, related_name='participations', to='group.groupmeeting')),
                ('member', models.ForeignKey(help_text='Group member', on_delete=django.db.models.deletion.CASCADE, related_name='meeting_participations', to='group.groupmember')),
            ],
            options={
                'verbose_name': 'Group Meeting Participation',
                'verbose_name_plural': 'Group Meeting Participations',
                'ordering': ['member__user__last_name', 'member__user__first_name'],
            },
        ),
        migrations.AddConstraint(
            model_name='groupmeetingparticipation',
            constraint=models.UniqueConstraint(fields=('meeting', 'member'), name='group_groupmeetingparticipation_meeting_member_uniq'),
        ),
    ]
