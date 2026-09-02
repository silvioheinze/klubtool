"""Tests for the district events MCP server."""

import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from district.models import District, DistrictEvent, Party
from group.models import Group, GroupMember
from user.models import McpToken, Role

User = get_user_model()


class McpDistrictEventTests(TestCase):
    """MCP JSON-RPC tools for district events."""

    def setUp(self):
        self.client = Client()
        self.member = User.objects.create_user(
            username='mcp_member',
            email='mcp_member@example.com',
            password='memberpass123',
        )
        self.manager = User.objects.create_user(
            username='mcp_manager',
            email='mcp_manager@example.com',
            password='managerpass123',
        )
        self.district = District.objects.create(
            name='MCP District',
            code='MCP',
            description='Test district',
            is_active=True,
        )
        self.party = Party.objects.create(
            name='MCP Party',
            district=self.district,
            is_active=True,
        )
        self.group = Group.objects.create(
            name='MCP Group',
            party=self.party,
            is_active=True,
        )
        GroupMember.objects.create(user=self.member, group=self.group, is_active=True)
        leader_role = Role.objects.get_or_create(name='Leader', defaults={'is_active': True})[0]
        manager_membership = GroupMember.objects.create(
            user=self.manager, group=self.group, is_active=True,
        )
        manager_membership.roles.add(leader_role)
        _, self.manager_token = McpToken.create_token(self.manager)
        _, self.member_token = McpToken.create_token(self.member)

    def _rpc(self, method, params=None, token=None, request_id=1):
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'} if token else {}
        payload = {
            'jsonrpc': '2.0',
            'id': request_id,
            'method': method,
            'params': params or {},
        }
        return self.client.post(
            reverse('mcp'),
            data=json.dumps(payload),
            content_type='application/json',
            **headers,
        )

    def _tool_call(self, name, arguments, token):
        response = self._rpc(
            'tools/call',
            {'name': name, 'arguments': arguments},
            token=token,
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertNotIn('error', body)
        result = body['result']
        text = result['content'][0]['text']
        return json.loads(text), result.get('isError', False)

    def test_unauthorized_without_token(self):
        response = self._rpc('tools/list')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error']['code'], -32001)

    def test_initialize_returns_server_info(self):
        response = self._rpc('initialize', token=self.manager_token)
        self.assertEqual(response.status_code, 200)
        result = response.json()['result']
        self.assertEqual(result['serverInfo']['name'], 'klubtool')
        self.assertIn('tools', result['capabilities'])

    def test_tools_list_includes_create(self):
        response = self._rpc('tools/list', token=self.manager_token)
        names = [tool['name'] for tool in response.json()['result']['tools']]
        self.assertIn('create_district_event', names)

    def test_manager_can_create_event(self):
        scheduled = (timezone.now() + timedelta(days=3)).replace(microsecond=0)
        data, is_error = self._tool_call(
            'create_district_event',
            {
                'district_id': self.district.pk,
                'title': 'MCP Meetup',
                'scheduled_date': scheduled.isoformat(),
                'description': 'Created via MCP',
            },
            self.manager_token,
        )
        self.assertFalse(is_error)
        event = DistrictEvent.objects.get(pk=data['event']['id'])
        self.assertEqual(event.title, 'MCP Meetup')
        self.assertEqual(event.created_by, self.manager)

    def test_member_cannot_create_event(self):
        scheduled = (timezone.now() + timedelta(days=3)).isoformat()
        data, is_error = self._tool_call(
            'create_district_event',
            {
                'district_id': self.district.pk,
                'title': 'Forbidden',
                'scheduled_date': scheduled,
            },
            self.member_token,
        )
        self.assertTrue(is_error)
        self.assertIn('permission', data['error'].lower())

    def test_list_and_get_event(self):
        event = DistrictEvent.objects.create(
            title='Listed Event',
            district=self.district,
            scheduled_date=timezone.now() + timedelta(days=5),
            created_by=self.manager,
        )
        listed, _ = self._tool_call(
            'list_district_events',
            {'district_id': self.district.pk},
            self.member_token,
        )
        self.assertEqual(len(listed['events']), 1)
        fetched, _ = self._tool_call(
            'get_district_event',
            {'event_id': event.pk},
            self.member_token,
        )
        self.assertEqual(fetched['event']['title'], 'Listed Event')

    def test_manager_can_update_and_delete(self):
        event = DistrictEvent.objects.create(
            title='Old Title',
            district=self.district,
            scheduled_date=timezone.now() + timedelta(days=5),
            created_by=self.manager,
        )
        updated, is_error = self._tool_call(
            'update_district_event',
            {'event_id': event.pk, 'title': 'New Title'},
            self.manager_token,
        )
        self.assertFalse(is_error)
        event.refresh_from_db()
        self.assertEqual(event.title, 'New Title')

        deleted, is_error = self._tool_call(
            'delete_district_event',
            {'event_id': event.pk},
            self.manager_token,
        )
        self.assertFalse(is_error)
        self.assertFalse(DistrictEvent.objects.filter(pk=event.pk).exists())

    def test_member_cannot_delete_event(self):
        event = DistrictEvent.objects.create(
            title='Protected',
            district=self.district,
            scheduled_date=timezone.now() + timedelta(days=5),
            created_by=self.manager,
        )
        _, is_error = self._tool_call(
            'delete_district_event',
            {'event_id': event.pk},
            self.member_token,
        )
        self.assertTrue(is_error)
        self.assertTrue(DistrictEvent.objects.filter(pk=event.pk).exists())


class McpTokenSettingsTests(TestCase):
    """MCP token creation via user settings."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='tokenuser',
            email='tokenuser@example.com',
            password='pass123456',
        )

    def test_create_token_stores_hash_only(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('mcp-token-create'))
        self.assertEqual(response.status_code, 302)
        token = McpToken.objects.get(user=self.user, is_active=True)
        self.assertEqual(len(token.token_hash), 64)
        settings_response = self.client.get(reverse('user-settings'))
        self.assertContains(settings_response, 'Bearer')

    def test_lookup_finds_active_token(self):
        _, raw = McpToken.create_token(self.user)
        found = McpToken.lookup(raw)
        self.assertIsNotNone(found)
        self.assertEqual(found.user, self.user)

    def test_inactive_user_token_rejected(self):
        _, raw = McpToken.create_token(self.user)
        self.user.is_active = False
        self.user.save()
        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'ping',
            'params': {},
        }
        response = self.client.post(
            reverse('mcp'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {raw}',
        )
        self.assertEqual(response.status_code, 401)
