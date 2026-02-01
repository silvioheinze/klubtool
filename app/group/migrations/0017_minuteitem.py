# Generated manually for MinuteItem model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0016_add_group_calendar_badge_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MinuteItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(help_text='Title of the minute item', max_length=200)),
                ('description', models.TextField(blank=True, help_text='Description or notes for the minute item')),
                ('order', models.PositiveIntegerField(default=0, help_text='Order of the minute item within the meeting')),
                ('is_active', models.BooleanField(default=True, help_text='Whether the minute item is currently active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created the minute item', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_minute_items', to=settings.AUTH_USER_MODEL)),
                ('meeting', models.ForeignKey(help_text='Meeting this minute item belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='minute_items', to='group.groupmeeting')),
                ('parent_item', models.ForeignKey(blank=True, help_text='Parent minute item if this is a sub-item', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='sub_items', to='group.minuteitem')),
            ],
            options={
                'verbose_name': 'Minute Item',
                'verbose_name_plural': 'Minute Items',
                'ordering': ['order', 'created_at'],
            },
        ),
    ]
