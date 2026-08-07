from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='McpExposedModel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('app_label', models.CharField(max_length=100)),
                ('model_name', models.CharField(max_length=100)),
                ('allow_query', models.BooleanField(default=False)),
                ('allow_create', models.BooleanField(default=False)),
                ('allow_update', models.BooleanField(default=False)),
                ('allow_delete', models.BooleanField(default=False)),
                ('exclude_fields', models.JSONField(blank=True, default=list)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'MCP exposed model',
                'verbose_name_plural': 'MCP exposed models',
                'ordering': ['app_label', 'model_name'],
                'unique_together': {('app_label', 'model_name')},
            },
        ),
    ]
