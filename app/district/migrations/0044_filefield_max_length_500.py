from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('district', '0043_alter_districteventattachment_file_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='committeemeetingattachment',
            name='file',
            field=models.FileField(max_length=500, upload_to='committee_meeting_attachments/%Y/%m/%d/'),
        ),
        migrations.AlterField(
            model_name='sessionattachment',
            name='file',
            field=models.FileField(max_length=500, upload_to='session_attachments/%Y/%m/%d/'),
        ),
        migrations.AlterField(
            model_name='districteventattachment',
            name='file',
            field=models.FileField(max_length=500, upload_to='district_event_attachments/%Y/%m/%d/'),
        ),
    ]
