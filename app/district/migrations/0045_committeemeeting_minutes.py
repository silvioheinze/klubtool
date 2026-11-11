from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('district', '0044_filefield_max_length_500'),
    ]

    operations = [
        migrations.AddField(
            model_name='committeemeeting',
            name='minutes',
            field=models.TextField(blank=True, help_text='Minutes / protocol from the meeting'),
        ),
    ]
