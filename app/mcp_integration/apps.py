from django.apps import AppConfig


class McpIntegrationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mcp_integration'

    def ready(self):
        from .registry import register_enabled_models

        register_enabled_models()
