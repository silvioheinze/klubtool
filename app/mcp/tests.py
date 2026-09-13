"""Tests for the district events MCP server."""

import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from district.models import Council, District, DistrictEvent, Party, Session, Term
from group.models import Group, GroupMember
from motion.models import Inquiry, Motion
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


class McpMotionInquiryTests(TestCase):
    """MCP JSON-RPC tools for motions and inquiries."""

    def setUp(self):
        self.client = Client()
        self.member = User.objects.create_user(
            username='motion_member',
            email='motion_member@example.com',
            password='memberpass123',
        )
        self.outsider = User.objects.create_user(
            username='motion_outsider',
            email='motion_outsider@example.com',
            password='outsiderpass123',
        )
        self.district = District.objects.create(
            name='Motion MCP District',
            code='MMD',
            description='Test district',
            is_active=True,
        )
        self.other_district = District.objects.create(
            name='Other District',
            code='OTH',
            description='Other district',
            is_active=True,
        )
        self.party = Party.objects.create(
            name='Motion MCP Party',
            district=self.district,
            is_active=True,
        )
        self.other_party = Party.objects.create(
            name='Other Party',
            district=self.other_district,
            is_active=True,
        )
        self.group = Group.objects.create(
            name='Motion MCP Group',
            party=self.party,
            is_active=True,
        )
        self.other_group = Group.objects.create(
            name='Other Group',
            party=self.other_party,
            is_active=True,
        )
        GroupMember.objects.create(user=self.member, group=self.group, is_active=True)
        self.council, _ = Council.objects.get_or_create(
            district=self.district,
            defaults={'name': 'Motion MCP Council', 'is_active': True},
        )
        self.other_council, _ = Council.objects.get_or_create(
            district=self.other_district,
            defaults={'name': 'Other Council', 'is_active': True},
        )
        self.term = Term.objects.create(
            name='MCP Term',
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timedelta(days=365)).date(),
        )
        self.session = Session.objects.create(
            title='MCP Session',
            council=self.council,
            term=self.term,
            scheduled_date=timezone.now() + timedelta(days=7),
            is_active=True,
        )
        self.other_session = Session.objects.create(
            title='Other Session',
            council=self.other_council,
            term=self.term,
            scheduled_date=timezone.now() + timedelta(days=7),
            is_active=True,
        )
        _, self.member_token = McpToken.create_token(self.member)
        _, self.outsider_token = McpToken.create_token(self.outsider)

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

    def test_tools_list_includes_motion_and_inquiry_tools(self):
        response = self._rpc('tools/list', token=self.member_token)
        names = [tool['name'] for tool in response.json()['result']['tools']]
        for tool_name in (
            'list_motions',
            'list_inquiries',
            'create_motion',
            'update_motion',
            'get_motion',
            'create_inquiry',
            'update_inquiry',
            'get_inquiry',
        ):
            self.assertIn(tool_name, names)

    def test_member_can_create_motion_and_inquiry(self):
        motion_data, motion_error = self._tool_call(
            'create_motion',
            {
                'title': 'MCP Motion',
                'session_id': self.session.pk,
                'text': 'Motion text',
                'party_ids': [self.party.pk],
            },
            self.member_token,
        )
        self.assertFalse(motion_error)
        motion = Motion.objects.get(pk=motion_data['motion']['id'])
        self.assertEqual(motion.title, 'MCP Motion')
        self.assertEqual(motion.status, 'draft')
        self.assertEqual(motion.submitted_by, self.member)
        self.assertEqual(motion.interventions.count(), 0)

        inquiry_data, inquiry_error = self._tool_call(
            'create_inquiry',
            {
                'title': 'MCP Inquiry',
                'session_id': self.session.pk,
                'text': 'Inquiry text',
                'party_ids': [self.party.pk],
            },
            self.outsider_token,
        )
        self.assertTrue(inquiry_error)
        self.assertIn('permission', inquiry_data['error'].lower())

        inquiry_data, inquiry_error = self._tool_call(
            'create_inquiry',
            {
                'title': 'MCP Inquiry',
                'session_id': self.session.pk,
                'text': 'Inquiry text',
                'party_ids': [self.party.pk],
            },
            self.member_token,
        )
        self.assertFalse(inquiry_error)
        inquiry = Inquiry.objects.get(pk=inquiry_data['inquiry']['id'])
        self.assertEqual(inquiry.title, 'MCP Inquiry')
        self.assertEqual(inquiry.submitted_by, self.member)

    def test_outsider_cannot_create_motion(self):
        data, is_error = self._tool_call(
            'create_motion',
            {
                'title': 'Forbidden Motion',
                'session_id': self.session.pk,
            },
            self.outsider_token,
        )
        self.assertTrue(is_error)
        self.assertIn('permission', data['error'].lower())
        self.assertFalse(Motion.objects.filter(title='Forbidden Motion').exists())

    def test_member_can_update_own_group_motion_outsider_cannot(self):
        motion = Motion.objects.create(
            title='Existing Motion',
            text='Body',
            session=self.session,
            group=self.group,
            submitted_by=self.member,
            status='draft',
        )
        motion.parties.add(self.party)

        updated, is_error = self._tool_call(
            'update_motion',
            {
                'motion_id': motion.pk,
                'title': 'Updated Motion',
                'intervention_ids': [self.member.pk],
            },
            self.member_token,
        )
        self.assertFalse(is_error)
        motion.refresh_from_db()
        self.assertEqual(motion.title, 'Updated Motion')
        self.assertEqual(list(motion.interventions.values_list('pk', flat=True)), [self.member.pk])

        denied, is_error = self._tool_call(
            'update_motion',
            {'motion_id': motion.pk, 'title': 'Hacked'},
            self.outsider_token,
        )
        self.assertTrue(is_error)
        self.assertIn('permission', denied['error'].lower())
        motion.refresh_from_db()
        self.assertEqual(motion.title, 'Updated Motion')

    def test_member_can_get_and_update_inquiry_outsider_denied(self):
        inquiry = Inquiry.objects.create(
            title='Existing Inquiry',
            text='Question',
            session=self.session,
            group=self.group,
            submitted_by=self.member,
            status='draft',
        )
        inquiry.parties.add(self.party)

        fetched, is_error = self._tool_call(
            'get_inquiry',
            {'inquiry_id': inquiry.pk},
            self.member_token,
        )
        self.assertFalse(is_error)
        self.assertEqual(fetched['inquiry']['title'], 'Existing Inquiry')

        updated, is_error = self._tool_call(
            'update_inquiry',
            {'inquiry_id': inquiry.pk, 'answer': 'Written answer'},
            self.member_token,
        )
        self.assertFalse(is_error)
        inquiry.refresh_from_db()
        self.assertEqual(inquiry.answer, 'Written answer')

        denied, is_error = self._tool_call(
            'get_inquiry',
            {'inquiry_id': inquiry.pk},
            self.outsider_token,
        )
        self.assertTrue(is_error)
        self.assertIn('permission', denied['error'].lower())

    def test_invalid_session_group_district_returns_form_error(self):
        data, is_error = self._tool_call(
            'create_motion',
            {
                'title': 'Bad District Motion',
                'session_id': self.other_session.pk,
                'group_id': self.group.pk,
            },
            self.member_token,
        )
        self.assertTrue(is_error)
        self.assertFalse(Motion.objects.filter(title='Bad District Motion').exists())

        data, is_error = self._tool_call(
            'create_inquiry',
            {
                'title': 'Bad District Inquiry',
                'session_id': self.other_session.pk,
                'group_id': self.group.pk,
            },
            self.member_token,
        )
        self.assertTrue(is_error)
        self.assertFalse(Inquiry.objects.filter(title='Bad District Inquiry').exists())

    def test_list_motions_and_inquiries_respects_group_access(self):
        own_motion = Motion.objects.create(
            title='Own Group Motion',
            text='Visible',
            session=self.session,
            group=self.group,
            submitted_by=self.member,
            status='draft',
        )
        other_motion = Motion.objects.create(
            title='Other Group Motion',
            text='Hidden',
            session=self.other_session,
            group=self.other_group,
            submitted_by=self.member,
            status='draft',
        )
        own_inquiry = Inquiry.objects.create(
            title='Own Group Inquiry',
            text='Visible inquiry',
            session=self.session,
            group=self.group,
            submitted_by=self.member,
            status='draft',
        )
        Inquiry.objects.create(
            title='Other Group Inquiry',
            text='Hidden inquiry',
            session=self.other_session,
            group=self.other_group,
            submitted_by=self.member,
            status='draft',
        )

        motions, is_error = self._tool_call('list_motions', {}, self.member_token)
        self.assertFalse(is_error)
        motion_ids = {item['id'] for item in motions['motions']}
        self.assertIn(own_motion.pk, motion_ids)
        self.assertNotIn(other_motion.pk, motion_ids)

        inquiries, is_error = self._tool_call('list_inquiries', {}, self.member_token)
        self.assertFalse(is_error)
        inquiry_ids = {item['id'] for item in inquiries['inquiries']}
        self.assertIn(own_inquiry.pk, inquiry_ids)
        self.assertEqual(inquiries['count'], 1)

    def test_outsider_cannot_list_motions_or_inquiries(self):
        Motion.objects.create(
            title='Any Motion',
            session=self.session,
            group=self.group,
            submitted_by=self.member,
            status='draft',
        )
        data, is_error = self._tool_call('list_motions', {}, self.outsider_token)
        self.assertTrue(is_error)
        self.assertIn('permission', data['error'].lower())

        data, is_error = self._tool_call('list_inquiries', {}, self.outsider_token)
        self.assertTrue(is_error)
        self.assertIn('permission', data['error'].lower())

    def test_list_motions_search_and_session_filter(self):
        Motion.objects.create(
            title='Housing Budget Motion',
            text='Details',
            session=self.session,
            group=self.group,
            submitted_by=self.member,
            status='draft',
        )
        Motion.objects.create(
            title='Unrelated Motion',
            text='Other',
            session=self.other_session,
            group=self.group,
            submitted_by=self.member,
            status='draft',
        )

        data, is_error = self._tool_call(
            'list_motions',
            {'search': 'Housing'},
            self.member_token,
        )
        self.assertFalse(is_error)
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['motions'][0]['title'], 'Housing Budget Motion')

        data, is_error = self._tool_call(
            'list_motions',
            {'session_id': self.session.pk},
            self.member_token,
        )
        self.assertFalse(is_error)
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['motions'][0]['session_id'], self.session.pk)


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

    def test_mcp_server_url_uses_https(self):
        self.client.force_login(self.user)
        self.client.get(reverse('mcp-token-create'))
        mcp_url = self.client.session['mcp_server_url']
        self.assertTrue(mcp_url.startswith('https://'))
        self.assertIn('/mcp/', mcp_url)

    def test_settings_page_documents_claude_setup(self):
        self.user.language = 'en'
        self.user.save()
        self.client.force_login(self.user)
        response = self.client.get(reverse('user-settings'))
        self.assertContains(response, 'Add in Claude')
        self.assertContains(response, 'Add custom connector')
        self.assertContains(response, 'claude mcp add')

    def test_lookup_finds_active_token(self):
        _, raw = McpToken.create_token(self.user)
        found = McpToken.lookup(raw)
        self.assertIsNotNone(found)
        self.assertEqual(found.user, self.user)

    def test_post_without_trailing_slash_accepts_jsonrpc(self):
        _, raw = McpToken.create_token(self.user)
        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'ping',
            'params': {},
        }
        response = self.client.post(
            '/mcp',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {raw}',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['result'], {})

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
