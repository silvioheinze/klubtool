import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('district', '0041_districtevent_end_date_location'),
    ]

    operations = [
        migrations.CreateModel(
            name='DistrictEventAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='district_event_attachments/%Y/%m/%d/')),
                ('filename', models.CharField(max_length=255)),
                ('file_type', models.CharField(
                    choices=[('invitation', 'Invitation'), ('other', 'Other')],
                    default='other',
                    max_length=20,
                )),
                ('description', models.TextField(blank=True)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('event', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='attachments',
                    to='district.districtevent',
                )),
                ('uploaded_by', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='district_event_attachments',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'District Event Attachment',
                'verbose_name_plural': 'District Event Attachments',
                'ordering': ['-uploaded_at'],
            },
        ),
    ]
