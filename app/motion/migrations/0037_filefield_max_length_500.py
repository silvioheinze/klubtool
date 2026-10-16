from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('motion', '0036_status_answer_files'),
    ]

    operations = [
        migrations.AlterField(
            model_name='motionattachment',
            name='file',
            field=models.FileField(max_length=500, upload_to='motion_attachments/%Y/%m/%d/'),
        ),
        migrations.AlterField(
            model_name='motionstatusanswerfile',
            name='file',
            field=models.FileField(max_length=500, upload_to='motion_answers/%Y/%m/%d/'),
        ),
        migrations.AlterField(
            model_name='inquirystatusanswerfile',
            name='file',
            field=models.FileField(max_length=500, upload_to='inquiry_answers/%Y/%m/%d/'),
        ),
        migrations.AlterField(
            model_name='inquiryattachment',
            name='file',
            field=models.FileField(max_length=500, upload_to='inquiry_attachments/%Y/%m/%d/'),
        ),
    ]
