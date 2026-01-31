# Generated manually for committee meeting attachments

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('local', '0026_alter_committeemember_joined_date_editable'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CommitteeMeetingAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='committee_meeting_attachments/%Y/%m/%d/')),
                ('filename', models.CharField(max_length=255)),
                ('file_type', models.CharField(
                    choices=[
                        ('agenda', 'Agenda'),
                        ('budget', 'Budget'),
                        ('invitation', 'Invitation'),
                        ('other', 'Other'),
                    ],
                    default='other',
                    max_length=20,
                )),
                ('description', models.TextField(blank=True)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('committee_meeting', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='attachments',
                    to='local.committeemeeting',
                )),
                ('uploaded_by', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='committee_meeting_attachments',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Committee Meeting Attachment',
                'verbose_name_plural': 'Committee Meeting Attachments',
                'ordering': ['-uploaded_at'],
            },
        ),
    ]
