import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('local', '0037_committeemeeting_status_remove_committee_status'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LocalEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(help_text='Title of the event', max_length=200)),
                ('scheduled_date', models.DateTimeField(help_text='Date and time of the event')),
                ('description', models.TextField(blank=True, help_text='Optional description or details')),
                ('external_link', models.URLField(blank=True, help_text='Optional external link for more information')),
                ('is_active', models.BooleanField(default=True, help_text='Whether the event is currently active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True,
                    help_text='User who created the event',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_local_events',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('local', models.ForeignKey(
                    help_text='District this event belongs to',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='events',
                    to='local.local',
                )),
            ],
            options={
                'verbose_name': 'District Event',
                'verbose_name_plural': 'District Events',
                'ordering': ['scheduled_date'],
            },
        ),
        migrations.CreateModel(
            name='LocalEventParticipation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('will_attend', models.BooleanField(default=False, help_text='Whether the user will attend')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('event', models.ForeignKey(
                    help_text='Event',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='participations',
                    to='local.localevent',
                )),
                ('user', models.ForeignKey(
                    help_text='User',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='local_event_participations',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'District Event Participation',
                'verbose_name_plural': 'District Event Participations',
                'ordering': ['user__last_name', 'user__first_name'],
            },
        ),
        migrations.AddConstraint(
            model_name='localeventparticipation',
            constraint=models.UniqueConstraint(
                fields=('event', 'user'),
                name='local_localeventparticipation_event_user_uniq',
            ),
        ),
    ]
