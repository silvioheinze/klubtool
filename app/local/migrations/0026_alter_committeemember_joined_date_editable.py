# Generated manually for editable joined_date

from datetime import date

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('local', '0025_add_committee_term'),
    ]

    operations = [
        migrations.AlterField(
            model_name='committeemember',
            name='joined_date',
            field=models.DateField(default=date.today, help_text='Date when the user joined the committee'),
        ),
    ]
