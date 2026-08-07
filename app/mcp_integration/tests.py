from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from mcp_server.query_tool import ModelQueryToolsetMeta
from rest_framework.authtoken.models import Token

from mcp_integration.model_discovery import get_discoverable_models, is_model_selectable
from mcp_integration.models import McpExposedModel
from mcp_integration.registry import register_enabled_models

User = get_user_model()


class McpModelDiscoveryTests(TestCase):
    def test_excluded_models_not_discoverable(self):
        discoverable = {(m.app_label, m.model_name) for m in get_discoverable_models()}
        self.assertNotIn(('user', 'CalendarSubscriptionToken'), discoverable)
        self.assertNotIn(('mcp_integration', 'McpExposedModel'), discoverable)
        self.assertFalse(is_model_selectable('user', 'CalendarSubscriptionToken'))

    def test_custom_user_is_discoverable_with_sensitive_flag(self):
        custom_users = [
            m for m in get_discoverable_models()
            if m.app_label == 'user' and m.model_name == 'CustomUser'
        ]
        self.assertEqual(len(custom_users), 1)
        self.assertTrue(custom_users[0].is_sensitive)


class McpSettingsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
        )
        self.user = User.objects.create_user(
            username='member',
            email='member@example.com',
            password='memberpass123',
        )
        self.url = reverse('mcp_integration:settings')

    def test_settings_page_superuser_only(self):
        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_save_model_config(self):
        self.client.force_login(self.superuser)
        response = self.client.post(self.url, {
            'save_models': '1',
            'query_local.Local': 'on',
            'create_local.Local': 'on',
            'update_local.Local': 'on',
        })
        self.assertEqual(response.status_code, 302)

        config = McpExposedModel.objects.get(app_label='local', model_name='Local')
        self.assertTrue(config.allow_query)
        self.assertTrue(config.allow_create)
        self.assertTrue(config.allow_update)
        self.assertFalse(config.allow_delete)

    def test_sensitive_model_writes_not_saved(self):
        self.client.force_login(self.superuser)
        self.client.post(self.url, {
            'save_models': '1',
            'query_user.CustomUser': 'on',
            'create_user.CustomUser': 'on',
            'update_user.CustomUser': 'on',
            'delete_user.CustomUser': 'on',
        })
        config = McpExposedModel.objects.get(app_label='user', model_name='CustomUser')
        self.assertTrue(config.allow_query)
        self.assertFalse(config.allow_create)
        self.assertFalse(config.allow_update)
        self.assertFalse(config.allow_delete)

    def test_create_token(self):
        self.client.force_login(self.superuser)
        response = self.client.post(self.url, {'create_token': '1'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Token.objects.filter(user=self.superuser).exists())

    def test_revoke_token(self):
        Token.objects.create(user=self.superuser)
        self.client.force_login(self.superuser)
        response = self.client.post(self.url, {'revoke_token': '1'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Token.objects.filter(user=self.superuser).exists())


class McpRegistryTests(TestCase):
    def setUp(self):
        from mcp_integration.registry import _clear_dynamic_registrations

        McpExposedModel.objects.all().delete()
        _clear_dynamic_registrations()

    def test_registry_registers_query_tool(self):
        McpExposedModel.objects.create(
            app_label='local',
            model_name='Local',
            allow_query=True,
        )
        register_enabled_models()
        self.assertIn('McpQuery_local_Local', ModelQueryToolsetMeta.registry)

    def test_registry_registers_write_tools(self):
        McpExposedModel.objects.create(
            app_label='local',
            model_name='Party',
            allow_create=True,
            allow_update=True,
        )
        register_enabled_models()
        from mcp_integration import registry as registry_module
        self.assertIn('McpCreate_local_Party', registry_module._registered_dynamic_classes)
        self.assertIn('McpUpdate_local_Party', registry_module._registered_dynamic_classes)


class McpEndpointAuthTests(TestCase):
    def test_mcp_endpoint_requires_token(self):
        response = Client().post(
            '/mcp',
            data='{"jsonrpc":"2.0","method":"initialize","id":1,"params":{}}',
            content_type='application/json',
        )
        self.assertIn(response.status_code, (401, 403))

    def test_mcp_endpoint_accepts_token(self):
        user = User.objects.create_superuser(
            username='mcpadmin',
            email='mcp@example.com',
            password='adminpass123',
        )
        token = Token.objects.create(user=user)
        response = Client().post(
            '/mcp',
            data='{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}',
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {token.key}',
        )
        self.assertNotIn(response.status_code, (401, 403))
