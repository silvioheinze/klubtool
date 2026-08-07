from django.contrib import admin

from .models import McpExposedModel


@admin.register(McpExposedModel)
class McpExposedModelAdmin(admin.ModelAdmin):
    list_display = (
        'app_label',
        'model_name',
        'allow_query',
        'allow_create',
        'allow_update',
        'allow_delete',
        'updated_at',
    )
    list_filter = ('app_label', 'allow_query', 'allow_create', 'allow_update', 'allow_delete')
    search_fields = ('app_label', 'model_name')
