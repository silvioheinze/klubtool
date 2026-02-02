# Generated manually for CommitteeParticipationSubstitute

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('local', '0030_add_council_calendar_badge_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommitteeParticipationSubstitute',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('committee_meeting', models.ForeignKey(help_text='Committee meeting', on_delete=django.db.models.deletion.CASCADE, related_name='participation_substitutes', to='local.committeemeeting')),
                ('member', models.ForeignKey(help_text='Regular member who will not attend (replaced by substitute)', on_delete=django.db.models.deletion.CASCADE, related_name='meeting_substitutions_as_member', to='local.committeemember')),
                ('substitute_member', models.ForeignKey(help_text='Substitute member who will attend in place of the member', on_delete=django.db.models.deletion.CASCADE, related_name='meeting_substitutions_as_substitute', to='local.committeemember')),
            ],
            options={
                'verbose_name': 'Committee participation substitute',
                'verbose_name_plural': 'Committee participation substitutes',
            },
        ),
        migrations.AddConstraint(
            model_name='committeeparticipationsubstitute',
            constraint=models.UniqueConstraint(fields=('committee_meeting', 'member'), name='local_committeeparticipation_meeting_member_uniq'),
        ),
        migrations.AddConstraint(
            model_name='committeeparticipationsubstitute',
            constraint=models.UniqueConstraint(fields=('committee_meeting', 'substitute_member'), name='local_committeeparticipation_meeting_sub_uniq'),
        ),
    ]
