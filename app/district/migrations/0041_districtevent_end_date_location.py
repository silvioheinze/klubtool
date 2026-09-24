from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('district', '0040_add_committee_membership_period'),
    ]

    operations = [
        migrations.AddField(
            model_name='districtevent',
            name='end_date',
            field=models.DateTimeField(
                blank=True,
                help_text='Optional end date and time (must be after start)',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='districtevent',
            name='location',
            field=models.CharField(
                blank=True,
                help_text='Location or place of the event',
                max_length=300,
            ),
        ),
    ]
