from django.core.management.base import BaseCommand

from mcp_integration.registry import register_enabled_models


class Command(BaseCommand):
    help = 'Reload MCP model tool registrations from database configuration.'

    def handle(self, *args, **options):
        register_enabled_models()
        self.stdout.write(self.style.SUCCESS('MCP query tools reloaded from database.'))
        self.stdout.write(
            'Write tools (create/update/delete) require a full server restart to reload.'
        )
