# Generated manually for SessionExcuse

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('local', '0030_add_council_calendar_badge_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SessionExcuse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('note', models.TextField(blank=True, help_text='Optional reason or note')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('session', models.ForeignKey(help_text='Council session', on_delete=django.db.models.deletion.CASCADE, related_name='excuses', to='local.session')),
                ('user', models.ForeignKey(help_text='User who excused themselves', on_delete=django.db.models.deletion.CASCADE, related_name='session_excuses', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Session excuse',
                'verbose_name_plural': 'Session excuses',
            },
        ),
        migrations.AddConstraint(
            model_name='sessionexcuse',
            constraint=models.UniqueConstraint(fields=('session', 'user'), name='local_sessionexcuse_session_user_uniq'),
        ),
    ]
