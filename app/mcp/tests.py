"""Tests for the district events MCP server."""

import base64
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from district.models import (
    Committee,
    CommitteeMeeting,
    CommitteeMeetingAttachment,
    CommitteeMember,
    Council,
    District,
    DistrictEvent,
    DistrictEventAttachment,
    Party,
    Session,
    SessionAttachment,
    Term,
    TermSeatDistribution,
)
from group.models import Group, GroupMember
from motion.models import (
    Inquiry,
    InquiryAttachment,
    Motion,
    MotionAttachment,
    MotionStatus,
    MotionVote,
    Tag,
)
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
        self.superuser = User.objects.create_superuser(
            username='mcp_event_super',
            email='mcp_event_super@example.com',
            password='superpass123',
        )
        self.outsider = User.objects.create_user(
            username='mcp_event_outsider',
            email='mcp_event_outsider@example.com',
            password='outsiderpass123',
        )
        _, self.manager_token = McpToken.create_token(self.manager)
        _, self.member_token = McpToken.create_token(self.member)
        _, self.superuser_token = McpToken.create_token(self.superuser)
        _, self.outsider_token = McpToken.create_token(self.outsider)

    def _attachment_event(self):
        return DistrictEvent.objects.create(
            title='Attachment Event',
            district=self.district,
            scheduled_date=timezone.now() + timedelta(days=4),
            created_by=self.manager,
        )

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
        self.assertIn('create_district_event_upload_url', names)

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

    def test_create_upload_url_superuser_and_manager(self):
        event = self._attachment_event()
        for token in (self.superuser_token, self.manager_token):
            data, is_error = self._tool_call(
                'create_district_event_upload_url',
                {
                    'event_id': event.pk,
                    'filename': 'agenda.pdf',
                    'file_type': 'agenda',
                },
                token,
            )
            self.assertFalse(is_error, data)
            self.assertTrue(data['upload_url'].startswith('https://'))
            self.assertEqual(data['event_id'], event.pk)
            self.assertEqual(data['method'], 'PUT')
            self.assertEqual(data['expires_in'], 600)
            self.assertEqual(data['max_bytes'], 25 * 1024 * 1024)

    def test_create_upload_url_member_denied(self):
        event = self._attachment_event()
        data, is_error = self._tool_call(
            'create_district_event_upload_url',
            {
                'event_id': event.pk,
                'filename': 'agenda.pdf',
            },
            self.member_token,
        )
        self.assertTrue(is_error)
        self.assertIn('permission', data['error'].lower())

    def test_create_upload_url_invalid_extension(self):
        event = self._attachment_event()
        data, is_error = self._tool_call(
            'create_district_event_upload_url',
            {
                'event_id': event.pk,
                'filename': 'bad.exe',
            },
            self.manager_token,
        )
        self.assertTrue(is_error)
        self.assertIn('not allowed', data['error'].lower())

    def test_list_and_delete_district_event_attachment(self):
        event = self._attachment_event()
        pdf_bytes = b'%PDF-1.4 district event list'
        attachment = DistrictEventAttachment.objects.create(
            event=event,
            file=SimpleUploadedFile('listed.pdf', pdf_bytes),
            filename='listed.pdf',
            file_type='agenda',
            uploaded_by=self.manager,
        )

        list_data, list_error = self._tool_call(
            'list_attachments',
            {'parent_type': 'district_event', 'parent_id': event.pk},
            self.member_token,
        )
        self.assertFalse(list_error)
        self.assertEqual(len(list_data['attachments']), 1)
        self.assertEqual(list_data['attachments'][0]['id'], attachment.pk)

        denied, is_error = self._tool_call(
            'list_attachments',
            {'parent_type': 'district_event', 'parent_id': event.pk},
            self.outsider_token,
        )
        self.assertTrue(is_error)
        self.assertIn('access', denied['error'].lower())

        delete_denied, is_error = self._tool_call(
            'delete_attachment',
            {'parent_type': 'district_event', 'attachment_id': attachment.pk},
            self.outsider_token,
        )
        self.assertTrue(is_error)
        self.assertIn('permission', delete_denied['error'].lower())
        self.assertTrue(DistrictEventAttachment.objects.filter(pk=attachment.pk).exists())

        deleted, is_error = self._tool_call(
            'delete_attachment',
            {'parent_type': 'district_event', 'attachment_id': attachment.pk},
            self.manager_token,
        )
        self.assertFalse(is_error)
        self.assertTrue(deleted['deleted'])
        self.assertFalse(DistrictEventAttachment.objects.filter(pk=attachment.pk).exists())


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
            'upload_session_attachment',
            'upload_motion_attachment',
            'upload_inquiry_attachment',
            'upload_committee_meeting_attachment',
            'create_committee_meeting_upload_url',
            'create_district_event_upload_url',
            'create_motion_upload_url',
            'create_inquiry_upload_url',
            'list_parties',
            'list_tags',
            'list_committees',
            'list_committee_meetings',
            'list_sessions',
            'get_committee_meeting',
            'update_committee_meeting',
            'list_attachments',
            'delete_attachment',
        ):
            self.assertIn(tool_name, names)

    def test_member_can_create_motion_and_inquiry(self):
        motion_data, motion_error = self._tool_call(
            'create_motion',
            {
                'title': 'MCP Motion',
                'file_number': 'BV-2025-01',
                'session_id': self.session.pk,
                'text': 'Motion text',
                'party_ids': [self.party.pk],
            },
            self.member_token,
        )
        self.assertFalse(motion_error)
        self.assertEqual(motion_data['motion']['file_number'], 'BV-2025-01')
        motion = Motion.objects.get(pk=motion_data['motion']['id'])
        self.assertEqual(motion.title, 'MCP Motion')
        self.assertEqual(motion.file_number, 'BV-2025-01')
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

    def test_list_parties_in_district_with_search(self):
        second_party = Party.objects.create(
            name='Alpha List Party',
            short_name='ALP',
            district=self.district,
            is_active=True,
            color='#112233',
        )
        data, is_error = self._tool_call(
            'list_parties',
            {'district_id': self.district.pk},
            self.member_token,
        )
        self.assertFalse(is_error)
        ids = {p['id'] for p in data['parties']}
        self.assertIn(self.party.pk, ids)
        self.assertIn(second_party.pk, ids)
        self.assertEqual(
            next(p for p in data['parties'] if p['id'] == second_party.pk)['short_name'],
            'ALP',
        )

        filtered, is_error = self._tool_call(
            'list_parties',
            {'district_id': self.district.pk, 'search': 'Alpha'},
            self.member_token,
        )
        self.assertFalse(is_error)
        self.assertEqual(len(filtered['parties']), 1)
        self.assertEqual(filtered['parties'][0]['id'], second_party.pk)

    def test_list_parties_denied_for_foreign_district(self):
        data, is_error = self._tool_call(
            'list_parties',
            {'district_id': self.other_district.pk},
            self.member_token,
        )
        self.assertTrue(is_error)
        self.assertIn('access', data['error'].lower())

    def test_list_tags_with_search(self):
        Tag.objects.create(name='Zebra MCP Tag', slug='zebra-mcp-tag', is_active=True)
        housing = Tag.objects.create(name='Housing MCP', slug='housing-mcp', is_active=True)
        Tag.objects.create(name='Inactive Tag', slug='inactive-tag', is_active=False)

        data, is_error = self._tool_call('list_tags', {}, self.member_token)
        self.assertFalse(is_error)
        names = [t['name'] for t in data['tags']]
        self.assertIn('Housing MCP', names)
        self.assertIn('Zebra MCP Tag', names)
        self.assertNotIn('Inactive Tag', names)

        filtered, is_error = self._tool_call(
            'list_tags',
            {'search': 'Hous'},
            self.member_token,
        )
        self.assertFalse(is_error)
        self.assertEqual(len(filtered['tags']), 1)
        self.assertEqual(filtered['tags'][0]['id'], housing.pk)
        self.assertEqual(filtered['tags'][0]['slug'], 'housing-mcp')

    def test_list_motions_search_matches_file_number(self):
        Motion.objects.create(
            title='File Number Motion',
            file_number='BV-2025-42',
            text='Body',
            session=self.session,
            group=self.group,
            submitted_by=self.member,
            status='draft',
        )

        data, is_error = self._tool_call(
            'list_motions',
            {'search': 'BV-2025-42'},
            self.member_token,
        )
        self.assertFalse(is_error)
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['motions'][0]['file_number'], 'BV-2025-42')


class McpMotionStatusChangeTests(TestCase):
    """MCP update_motion status_change (committee assignment and votes)."""

    def setUp(self):
        self.client = Client()
        self.member = User.objects.create_user(
            username='status_mcp_member',
            email='status_mcp_member@example.com',
            password='memberpass123',
        )
        self.status_editor = User.objects.create_user(
            username='status_mcp_editor',
            email='status_mcp_editor@example.com',
            password='editorpass123',
        )
        self.district = District.objects.create(
            name='Status MCP District',
            code='SMD',
            description='Test district',
            is_active=True,
        )
        self.party = Party.objects.create(
            name='Status MCP Party',
            district=self.district,
            is_active=True,
        )
        self.other_party = Party.objects.create(
            name='Status MCP Other Party',
            district=self.district,
            is_active=True,
        )
        self.group = Group.objects.create(
            name='Status MCP Group',
            party=self.party,
            is_active=True,
        )
        GroupMember.objects.create(user=self.member, group=self.group, is_active=True)
        editor_membership = GroupMember.objects.create(
            user=self.status_editor,
            group=self.group,
            is_active=True,
        )
        motion_edit_role = Role.objects.create(
            name='Status MCP Motion Editor',
            is_active=True,
            permissions={'permissions': ['motion.edit', 'motion.view']},
        )
        editor_membership.roles.add(motion_edit_role)
        self.status_editor.role = motion_edit_role
        self.status_editor.save(update_fields=['role'])

        self.council, _ = Council.objects.get_or_create(
            district=self.district,
            defaults={'name': 'Status MCP Council', 'is_active': True},
        )
        self.term = Term.objects.create(
            name='Status MCP Term',
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timedelta(days=365)).date(),
        )
        self.session = Session.objects.create(
            title='Status MCP Session',
            council=self.council,
            term=self.term,
            scheduled_date=timezone.now() + timedelta(days=7),
            is_active=True,
        )
        self.committee = Committee.objects.create(
            name='Status MCP Committee',
            council=self.council,
            is_active=True,
        )
        TermSeatDistribution.objects.create(term=self.term, party=self.party, seats=10)
        TermSeatDistribution.objects.create(term=self.term, party=self.other_party, seats=8)

        _, self.member_token = McpToken.create_token(self.member)
        _, self.editor_token = McpToken.create_token(self.status_editor)

    def _tool_call(self, name, arguments, token):
        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {'name': name, 'arguments': arguments},
        }
        response = self.client.post(
            reverse('mcp'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        result = body['result']
        text = result['content'][0]['text']
        return json.loads(text), result.get('isError', False)

    def _create_motion(self, **kwargs):
        motion = Motion.objects.create(
            title=kwargs.get('title', 'Status Motion'),
            text='Body',
            session=self.session,
            group=self.group,
            submitted_by=self.status_editor,
            status=kwargs.get('status', 'submitted'),
            committee=kwargs.get('committee'),
        )
        motion.parties.add(self.party)
        return motion

    def test_refer_to_committee_with_majority_assigns_committee_and_records_votes(self):
        motion = self._create_motion()
        data, is_error = self._tool_call(
            'update_motion',
            {
                'motion_id': motion.pk,
                'status_change': {
                    'status': 'refer_to_committee',
                    'committee_id': self.committee.pk,
                    'votes': [
                        {'party_id': self.party.pk, 'stance': 'approve'},
                        {'party_id': self.other_party.pk, 'stance': 'reject'},
                    ],
                },
            },
            self.editor_token,
        )
        self.assertFalse(is_error)
        motion.refresh_from_db()
        self.assertEqual(motion.status, 'refer_to_committee')
        self.assertEqual(motion.committee_id, self.committee.pk)
        self.assertEqual(len(data['motion']['status_history']), 1)
        entry = data['motion']['status_history'][0]
        self.assertEqual(entry['status'], 'refer_to_committee')
        self.assertEqual(entry['committee_id'], self.committee.pk)
        self.assertEqual(len(entry['votes']), 2)
        party_vote = {v['party_id']: v for v in entry['votes']}
        self.assertEqual(party_vote[self.party.pk]['stance'], 'approve')
        self.assertEqual(party_vote[self.party.pk]['approve_votes'], 10)

    def test_refer_to_committee_without_majority_sets_refer_no_majority(self):
        motion = self._create_motion()
        data, is_error = self._tool_call(
            'update_motion',
            {
                'motion_id': motion.pk,
                'status_change': {
                    'status': 'refer_to_committee',
                    'committee_id': self.committee.pk,
                    'votes': [
                        {'party_id': self.party.pk, 'stance': 'reject'},
                        {'party_id': self.other_party.pk, 'stance': 'approve'},
                    ],
                },
            },
            self.editor_token,
        )
        self.assertFalse(is_error)
        motion.refresh_from_db()
        self.assertEqual(motion.status, 'refer_no_majority')
        self.assertIsNone(motion.committee_id)
        self.assertEqual(data['motion']['status_history'][0]['status'], 'refer_no_majority')
        self.assertEqual(len(data['motion']['status_history'][0]['votes']), 2)

    def test_voted_in_committee_requires_prior_referral(self):
        motion = self._create_motion()
        denied, is_error = self._tool_call(
            'update_motion',
            {
                'motion_id': motion.pk,
                'status_change': {
                    'status': 'voted_in_committee',
                    'committee_id': self.committee.pk,
                    'votes': [
                        {'party_id': self.party.pk, 'stance': 'approve'},
                    ],
                },
            },
            self.editor_token,
        )
        self.assertTrue(is_error)

        motion.status = 'refer_to_committee'
        motion.committee = self.committee
        motion.save()
        MotionStatus.objects.create(
            motion=motion,
            status='refer_to_committee',
            committee=self.committee,
        )

        data, is_error = self._tool_call(
            'update_motion',
            {
                'motion_id': motion.pk,
                'status_change': {
                    'status': 'voted_in_committee',
                    'committee_id': self.committee.pk,
                    'votes': [
                        {'party_id': self.party.pk, 'stance': 'approve'},
                    ],
                },
            },
            self.editor_token,
        )
        self.assertFalse(is_error)
        motion.refresh_from_db()
        self.assertEqual(motion.status, 'voted_in_committee')

    def test_excessive_votes_rejected(self):
        motion = self._create_motion()
        data, is_error = self._tool_call(
            'update_motion',
            {
                'motion_id': motion.pk,
                'status_change': {
                    'status': 'approved',
                    'votes': [
                        # Legacy counts over max seats (10) must fail
                        {'party_id': self.party.pk, 'approve_votes': 11, 'reject_votes': 0},
                    ],
                },
            },
            self.editor_token,
        )
        self.assertTrue(is_error)
        motion.refresh_from_db()
        self.assertEqual(motion.status, 'submitted')
        self.assertFalse(MotionVote.objects.filter(motion=motion).exists())

    def test_inquiry_answered_with_reason_does_not_require_pdf(self):
        self.status_editor.is_superuser = True
        self.status_editor.save(update_fields=['is_superuser'])
        inquiry = Inquiry.objects.create(
            title='Answer Inquiry',
            text='Question',
            session=self.session,
            group=self.group,
            submitted_by=self.status_editor,
            status='submitted',
        )
        data, is_error = self._tool_call(
            'update_inquiry',
            {
                'inquiry_id': inquiry.pk,
                'status_change': {
                    'status': 'answered',
                    'reason': 'Text answer',
                },
            },
            self.editor_token,
        )
        self.assertFalse(is_error, data)
        inquiry.refresh_from_db()
        self.assertEqual(inquiry.status, 'answered')
        self.assertEqual(inquiry.status_history.first().reason, 'Text answer')
        self.assertEqual(inquiry.status_history.first().answer_files.count(), 0)

    def test_member_without_status_permission_cannot_use_status_change(self):
        motion = self._create_motion()
        data, is_error = self._tool_call(
            'update_motion',
            {
                'motion_id': motion.pk,
                'title': 'Still editable?',
                'status_change': {
                    'status': 'approved',
                    'votes': [
                        {'party_id': self.party.pk, 'stance': 'approve'},
                    ],
                },
            },
            self.member_token,
        )
        self.assertTrue(is_error)
        self.assertIn('status', data['error'].lower())
        motion.refresh_from_db()
        self.assertEqual(motion.title, 'Status Motion')
        self.assertEqual(motion.status, 'submitted')

    def test_update_without_status_change_leaves_status_unchanged(self):
        motion = self._create_motion(status='draft')
        data, is_error = self._tool_call(
            'update_motion',
            {'motion_id': motion.pk, 'title': 'Renamed only'},
            self.member_token,
        )
        self.assertFalse(is_error)
        motion.refresh_from_db()
        self.assertEqual(motion.title, 'Renamed only')
        self.assertEqual(motion.status, 'draft')
        self.assertEqual(data['motion']['status_history'], [])


class McpAttachmentTests(TestCase):
    """MCP JSON-RPC tools for session, motion, and inquiry attachments."""

    PDF_BYTES = b'%PDF-1.4 test content'

    def setUp(self):
        self.client = Client()
        self.member = User.objects.create_user(
            username='attach_member',
            email='attach_member@example.com',
            password='memberpass123',
        )
        self.outsider = User.objects.create_user(
            username='attach_outsider',
            email='attach_outsider@example.com',
            password='outsiderpass123',
        )
        self.superuser = User.objects.create_superuser(
            username='attach_super',
            email='attach_super@example.com',
            password='superpass123',
        )
        self.district = District.objects.create(
            name='Attachment MCP District',
            code='AMD',
            description='Test district',
            is_active=True,
        )
        self.party = Party.objects.create(
            name='Attachment MCP Party',
            district=self.district,
            is_active=True,
        )
        self.group = Group.objects.create(
            name='Attachment MCP Group',
            party=self.party,
            is_active=True,
        )
        GroupMember.objects.create(user=self.member, group=self.group, is_active=True)
        self.council, _ = Council.objects.get_or_create(
            district=self.district,
            defaults={'name': 'Attachment MCP Council', 'is_active': True},
        )
        self.term = Term.objects.create(
            name='Attachment MCP Term',
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timedelta(days=365)).date(),
        )
        self.session = Session.objects.create(
            title='Attachment MCP Session',
            council=self.council,
            term=self.term,
            scheduled_date=timezone.now() + timedelta(days=7),
            is_active=True,
        )
        self.motion = Motion.objects.create(
            title='Attachment Motion',
            text='Body',
            session=self.session,
            group=self.group,
            submitted_by=self.member,
            status='draft',
        )
        self.inquiry = Inquiry.objects.create(
            title='Attachment Inquiry',
            text='Question',
            session=self.session,
            group=self.group,
            submitted_by=self.member,
            status='draft',
        )
        _, self.member_token = McpToken.create_token(self.member)
        _, self.outsider_token = McpToken.create_token(self.outsider)
        _, self.superuser_token = McpToken.create_token(self.superuser)
        self.pdf_base64 = base64.b64encode(self.PDF_BYTES).decode('ascii')

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

    def test_member_can_upload_motion_and_inquiry_attachments(self):
        motion_data, motion_error = self._tool_call(
            'upload_motion_attachment',
            {
                'motion_id': self.motion.pk,
                'filename': 'motion-doc.pdf',
                'content_base64': self.pdf_base64,
            },
            self.member_token,
        )
        self.assertFalse(motion_error)
        self.assertEqual(motion_data['attachment']['filename'], 'motion-doc.pdf')
        self.assertEqual(motion_data['attachment']['file_type'], 'document')
        self.assertTrue(MotionAttachment.objects.filter(motion=self.motion).exists())

        inquiry_data, inquiry_error = self._tool_call(
            'upload_inquiry_attachment',
            {
                'inquiry_id': self.inquiry.pk,
                'filename': 'inquiry-doc.pdf',
                'content_base64': self.pdf_base64,
            },
            self.member_token,
        )
        self.assertFalse(inquiry_error)
        self.assertEqual(inquiry_data['attachment']['filename'], 'inquiry-doc.pdf')
        self.assertTrue(InquiryAttachment.objects.filter(inquiry=self.inquiry).exists())

        fetched, is_error = self._tool_call(
            'get_motion',
            {'motion_id': self.motion.pk},
            self.member_token,
        )
        self.assertFalse(is_error)
        self.assertEqual(len(fetched['motion']['attachments']), 1)
        self.assertEqual(fetched['motion']['attachments'][0]['filename'], 'motion-doc.pdf')

    def test_outsider_cannot_upload_motion_or_inquiry_attachments(self):
        data, is_error = self._tool_call(
            'upload_motion_attachment',
            {
                'motion_id': self.motion.pk,
                'filename': 'forbidden.pdf',
                'content_base64': self.pdf_base64,
            },
            self.outsider_token,
        )
        self.assertTrue(is_error)
        self.assertIn('permission', data['error'].lower())
        self.assertFalse(MotionAttachment.objects.filter(motion=self.motion).exists())

        data, is_error = self._tool_call(
            'upload_inquiry_attachment',
            {
                'inquiry_id': self.inquiry.pk,
                'filename': 'forbidden.pdf',
                'content_base64': self.pdf_base64,
            },
            self.outsider_token,
        )
        self.assertTrue(is_error)
        self.assertIn('permission', data['error'].lower())
        self.assertFalse(InquiryAttachment.objects.filter(inquiry=self.inquiry).exists())

    def test_superuser_can_upload_session_attachment_member_cannot(self):
        data, is_error = self._tool_call(
            'upload_session_attachment',
            {
                'session_id': self.session.pk,
                'filename': 'agenda.pdf',
                'content_base64': self.pdf_base64,
                'file_type': 'agenda',
            },
            self.superuser_token,
        )
        self.assertFalse(is_error)
        self.assertEqual(data['attachment']['filename'], 'agenda.pdf')
        self.assertEqual(data['attachment']['file_type'], 'agenda')
        self.assertTrue(SessionAttachment.objects.filter(session=self.session).exists())

        denied, is_error = self._tool_call(
            'upload_session_attachment',
            {
                'session_id': self.session.pk,
                'filename': 'blocked.pdf',
                'content_base64': self.pdf_base64,
            },
            self.member_token,
        )
        self.assertTrue(is_error)
        self.assertIn('permission', denied['error'].lower())
        self.assertEqual(SessionAttachment.objects.filter(session=self.session).count(), 1)

    def test_invalid_file_extension_returns_form_error(self):
        data, is_error = self._tool_call(
            'upload_motion_attachment',
            {
                'motion_id': self.motion.pk,
                'filename': 'virus.exe',
                'content_base64': base64.b64encode(b'bad').decode('ascii'),
            },
            self.member_token,
        )
        self.assertTrue(is_error)
        self.assertIn('file', data['error'])
        self.assertFalse(MotionAttachment.objects.filter(motion=self.motion).exists())

    def test_create_motion_and_inquiry_upload_url_member(self):
        motion_url, motion_error = self._tool_call(
            'create_motion_upload_url',
            {
                'motion_id': self.motion.pk,
                'filename': 'motion-put.pdf',
                'file_type': 'document',
            },
            self.member_token,
        )
        self.assertFalse(motion_error, motion_url)
        self.assertTrue(motion_url['upload_url'].startswith('https://'))
        self.assertEqual(motion_url['motion_id'], self.motion.pk)
        self.assertEqual(motion_url['method'], 'PUT')
        self.assertEqual(motion_url['max_bytes'], 10 * 1024 * 1024)

        inquiry_url, inquiry_error = self._tool_call(
            'create_inquiry_upload_url',
            {
                'inquiry_id': self.inquiry.pk,
                'filename': 'inquiry-put.pdf',
            },
            self.member_token,
        )
        self.assertFalse(inquiry_error, inquiry_url)
        self.assertEqual(inquiry_url['inquiry_id'], self.inquiry.pk)
        self.assertEqual(inquiry_url['max_bytes'], 10 * 1024 * 1024)

    def test_create_upload_url_outsider_denied(self):
        for tool_name, args in (
            (
                'create_motion_upload_url',
                {'motion_id': self.motion.pk, 'filename': 'blocked.pdf'},
            ),
            (
                'create_inquiry_upload_url',
                {'inquiry_id': self.inquiry.pk, 'filename': 'blocked.pdf'},
            ),
        ):
            data, is_error = self._tool_call(tool_name, args, self.outsider_token)
            self.assertTrue(is_error)
            self.assertIn('permission', data['error'].lower())

    def test_create_motion_upload_url_invalid_extension(self):
        data, is_error = self._tool_call(
            'create_motion_upload_url',
            {
                'motion_id': self.motion.pk,
                'filename': 'bad.exe',
            },
            self.member_token,
        )
        self.assertTrue(is_error)
        self.assertIn('not allowed', data['error'].lower())


class McpCommitteeMeetingAttachmentTests(TestCase):
    """MCP JSON-RPC tool for committee meeting attachments."""

    PDF_BYTES = b'%PDF-1.4 test content'

    def setUp(self):
        self.client = Client()
        self.committee_member_user = User.objects.create_user(
            username='cm_member',
            email='cm_member@example.com',
            password='memberpass123',
        )
        self.group_leader = User.objects.create_user(
            username='cm_leader',
            email='cm_leader@example.com',
            password='leaderpass123',
        )
        self.outsider = User.objects.create_user(
            username='cm_outsider',
            email='cm_outsider@example.com',
            password='outsiderpass123',
        )
        self.superuser = User.objects.create_superuser(
            username='cm_super',
            email='cm_super@example.com',
            password='superpass123',
        )
        self.district = District.objects.create(
            name='CM MCP District',
            code='CMD',
            description='Test district',
            is_active=True,
        )
        self.party = Party.objects.create(
            name='CM MCP Party',
            district=self.district,
            is_active=True,
        )
        self.group = Group.objects.create(
            name='CM MCP Group',
            party=self.party,
            is_active=True,
        )
        GroupMember.objects.create(
            user=self.committee_member_user,
            group=self.group,
            is_active=True,
        )
        leader_membership = GroupMember.objects.create(
            user=self.group_leader,
            group=self.group,
            is_active=True,
        )
        leader_role = Role.objects.get_or_create(name='Leader', defaults={'is_active': True})[0]
        leader_membership.roles.add(leader_role)
        self.council, _ = Council.objects.get_or_create(
            district=self.district,
            defaults={'name': 'CM MCP Council', 'is_active': True},
        )
        self.committee = Committee.objects.create(
            name='CM MCP Committee',
            council=self.council,
            is_active=True,
        )
        CommitteeMember.objects.create(
            committee=self.committee,
            user=self.committee_member_user,
            role='member',
            is_active=True,
        )
        self.meeting = CommitteeMeeting.objects.create(
            committee=self.committee,
            title='CM MCP Meeting',
            scheduled_date=timezone.now() + timedelta(days=3),
            location='Room 101',
            description='Original agenda',
            status='scheduled',
            is_active=True,
        )
        _, self.leader_token = McpToken.create_token(self.group_leader)
        _, self.committee_member_token = McpToken.create_token(self.committee_member_user)
        _, self.outsider_token = McpToken.create_token(self.outsider)
        _, self.superuser_token = McpToken.create_token(self.superuser)
        self.pdf_base64 = base64.b64encode(self.PDF_BYTES).decode('ascii')

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

    def _upload(self, token, **extra):
        args = {
            'committee_meeting_id': self.meeting.pk,
            'filename': 'doc.pdf',
            'content_base64': self.pdf_base64,
        }
        args.update(extra)
        return self._tool_call('upload_committee_meeting_attachment', args, token)

    def test_superuser_and_group_leader_can_upload(self):
        data, is_error = self._upload(self.superuser_token, filename='super-agenda.pdf', file_type='agenda')
        self.assertFalse(is_error)
        self.assertEqual(data['attachment']['filename'], 'super-agenda.pdf')
        self.assertEqual(data['attachment']['file_type'], 'agenda')
        self.assertEqual(data['committee_meeting_id'], self.meeting.pk)
        self.assertEqual(data['meeting_status'], 'scheduled')

        data, is_error = self._upload(self.leader_token, filename='leader-invite.pdf', file_type='invitation')
        self.assertFalse(is_error)
        self.assertEqual(data['attachment']['filename'], 'leader-invite.pdf')
        self.assertTrue(
            CommitteeMeetingAttachment.objects.filter(committee_meeting=self.meeting).exists()
        )

    def test_outsider_cannot_upload(self):
        data, is_error = self._upload(self.outsider_token, filename='forbidden.pdf')
        self.assertTrue(is_error)
        self.assertIn('permission', data['error'].lower())
        self.assertFalse(
            CommitteeMeetingAttachment.objects.filter(committee_meeting=self.meeting).exists()
        )

    def test_minutes_sets_meeting_completed(self):
        data, is_error = self._upload(
            self.superuser_token,
            filename='protocol.pdf',
            file_type='minutes',
        )
        self.assertFalse(is_error)
        self.assertEqual(data['meeting_status'], 'completed')
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.status, 'completed')

    def test_invitation_sets_meeting_invited(self):
        data, is_error = self._upload(
            self.superuser_token,
            filename='invite.pdf',
            file_type='invitation',
        )
        self.assertFalse(is_error)
        self.assertEqual(data['meeting_status'], 'invited')
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.status, 'invited')

    def test_agenda_does_not_change_meeting_status(self):
        data, is_error = self._upload(
            self.superuser_token,
            filename='agenda.pdf',
            file_type='agenda',
        )
        self.assertFalse(is_error)
        self.assertEqual(data['meeting_status'], 'scheduled')
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.status, 'scheduled')

    def test_invalid_file_extension_returns_form_error(self):
        data, is_error = self._tool_call(
            'upload_committee_meeting_attachment',
            {
                'committee_meeting_id': self.meeting.pk,
                'filename': 'virus.exe',
                'content_base64': base64.b64encode(b'bad').decode('ascii'),
            },
            self.superuser_token,
        )
        self.assertTrue(is_error)
        self.assertIn('file', data['error'])
        self.assertFalse(
            CommitteeMeetingAttachment.objects.filter(committee_meeting=self.meeting).exists()
        )

    def test_create_upload_url_superuser_and_leader(self):
        for token in (self.superuser_token, self.leader_token):
            data, is_error = self._tool_call(
                'create_committee_meeting_upload_url',
                {
                    'committee_meeting_id': self.meeting.pk,
                    'filename': 'agenda.pdf',
                    'file_type': 'agenda',
                },
                token,
            )
            self.assertFalse(is_error, data)
            self.assertTrue(data['upload_url'].startswith('https://'))
            self.assertEqual(data['method'], 'PUT')
            self.assertEqual(data['expires_in'], 600)
            self.assertEqual(data['max_bytes'], 25 * 1024 * 1024)
            self.assertNotIn('content_base64', data)
            self.assertNotIn('file_url', data)

    def test_create_upload_url_outsider_denied(self):
        data, is_error = self._tool_call(
            'create_committee_meeting_upload_url',
            {
                'committee_meeting_id': self.meeting.pk,
                'filename': 'agenda.pdf',
            },
            self.outsider_token,
        )
        self.assertTrue(is_error)
        self.assertIn('permission', data['error'].lower())

    def test_create_upload_url_invalid_extension(self):
        data, is_error = self._tool_call(
            'create_committee_meeting_upload_url',
            {
                'committee_meeting_id': self.meeting.pk,
                'filename': 'bad.exe',
            },
            self.superuser_token,
        )
        self.assertTrue(is_error)
        self.assertIn('not allowed', data['error'].lower())

    def test_group_leader_can_update_committee_meeting_status_unchanged(self):
        self.meeting.status = 'invited'
        self.meeting.save(update_fields=['status'])

        data, is_error = self._tool_call(
            'update_committee_meeting',
            {
                'committee_meeting_id': self.meeting.pk,
                'title': 'Updated Meeting Title',
                'location': 'Room 202',
                'agenda': 'Updated agenda',
                'status': 'cancelled',
            },
            self.leader_token,
        )
        self.assertFalse(is_error)
        self.assertEqual(data['committee_meeting']['title'], 'Updated Meeting Title')
        self.assertEqual(data['committee_meeting']['location'], 'Room 202')
        self.assertEqual(data['committee_meeting']['agenda'], 'Updated agenda')
        self.assertEqual(data['committee_meeting']['status'], 'invited')

        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.title, 'Updated Meeting Title')
        self.assertEqual(self.meeting.location, 'Room 202')
        self.assertEqual(self.meeting.description, 'Updated agenda')
        self.assertEqual(self.meeting.status, 'invited')

    def test_update_committee_meeting_partial_fields_unchanged(self):
        data, is_error = self._tool_call(
            'update_committee_meeting',
            {
                'committee_meeting_id': self.meeting.pk,
                'location': 'Room 303',
            },
            self.leader_token,
        )
        self.assertFalse(is_error)
        self.assertEqual(data['committee_meeting']['location'], 'Room 303')
        self.assertEqual(data['committee_meeting']['title'], 'CM MCP Meeting')
        self.assertEqual(data['committee_meeting']['agenda'], 'Original agenda')

        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.location, 'Room 303')
        self.assertEqual(self.meeting.title, 'CM MCP Meeting')
        self.assertEqual(self.meeting.description, 'Original agenda')

    def test_committee_member_and_outsider_cannot_update_committee_meeting(self):
        for token in (self.committee_member_token, self.outsider_token):
            data, is_error = self._tool_call(
                'update_committee_meeting',
                {
                    'committee_meeting_id': self.meeting.pk,
                    'title': 'Hacked title',
                },
                token,
            )
            self.assertTrue(is_error)
            self.assertIn('permission', data['error'].lower())

        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.title, 'CM MCP Meeting')


class McpFileUrlUploadTests(TestCase):
    """MCP uploads via file_url with SSRF checks."""

    PDF_BYTES = b'%PDF-1.4 url upload'

    def setUp(self):
        self.client = Client()
        self.member = User.objects.create_user(
            username='url_member',
            email='url_member@example.com',
            password='memberpass123',
        )
        self.district = District.objects.create(
            name='URL MCP District',
            code='URLD',
            description='Test',
            is_active=True,
        )
        self.party = Party.objects.create(name='URL Party', district=self.district, is_active=True)
        self.group = Group.objects.create(name='URL Group', party=self.party, is_active=True)
        GroupMember.objects.create(user=self.member, group=self.group, is_active=True)
        self.council, _ = Council.objects.get_or_create(
            district=self.district,
            defaults={'name': 'URL Council', 'is_active': True},
        )
        self.term = Term.objects.create(
            name='URL Term',
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timedelta(days=365)).date(),
        )
        self.session = Session.objects.create(
            title='URL Session',
            council=self.council,
            term=self.term,
            scheduled_date=timezone.now() + timedelta(days=5),
            is_active=True,
        )
        self.motion = Motion.objects.create(
            title='URL Motion',
            text='Body',
            session=self.session,
            group=self.group,
            submitted_by=self.member,
            status='draft',
        )
        _, self.member_token = McpToken.create_token(self.member)

    def _tool_call(self, name, arguments, token):
        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {'name': name, 'arguments': arguments},
        }
        response = self.client.post(
            reverse('mcp'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        result = body['result']
        text = result['content'][0]['text']
        return json.loads(text), result.get('isError', False)

    def _mock_response(self, content, status_code=200):
        response = MagicMock()
        response.status_code = status_code
        response.headers = {}
        response.iter_content = lambda chunk_size: [content]
        response.close = MagicMock()
        return response

    @patch('mcp.tools._ensure_file_url_host_allowed')
    @patch('mcp.tools.requests.get')
    def test_upload_motion_via_file_url_returns_file_size(self, mock_get, _mock_host_ok):
        mock_get.return_value = self._mock_response(self.PDF_BYTES)
        data, is_error = self._tool_call(
            'upload_motion_attachment',
            {
                'motion_id': self.motion.pk,
                'filename': 'from-url.pdf',
                'file_url': 'https://files.example.com/doc.pdf',
            },
            self.member_token,
        )
        self.assertFalse(is_error)
        self.assertEqual(data['attachment']['filename'], 'from-url.pdf')
        self.assertEqual(data['attachment']['file_size'], len(self.PDF_BYTES))
        mock_get.assert_called_once()

    def test_rejects_http_file_url(self):
        data, is_error = self._tool_call(
            'upload_motion_attachment',
            {
                'motion_id': self.motion.pk,
                'filename': 'bad.pdf',
                'file_url': 'http://files.example.com/doc.pdf',
            },
            self.member_token,
        )
        self.assertTrue(is_error)
        self.assertIn('https', data['error'].lower())

    def test_rejects_loopback_file_url_host(self):
        data, is_error = self._tool_call(
            'upload_motion_attachment',
            {
                'motion_id': self.motion.pk,
                'filename': 'bad.pdf',
                'file_url': 'https://127.0.0.1/secret.pdf',
            },
            self.member_token,
        )
        self.assertTrue(is_error)
        self.assertIn('not allowed', data['error'].lower())

    def test_rejects_both_file_url_and_base64(self):
        data, is_error = self._tool_call(
            'upload_motion_attachment',
            {
                'motion_id': self.motion.pk,
                'filename': 'bad.pdf',
                'file_url': 'https://files.example.com/doc.pdf',
                'content_base64': base64.b64encode(self.PDF_BYTES).decode('ascii'),
            },
            self.member_token,
        )
        self.assertTrue(is_error)
        self.assertIn('not both', data['error'].lower())

    def test_requires_file_source(self):
        data, is_error = self._tool_call(
            'upload_motion_attachment',
            {
                'motion_id': self.motion.pk,
                'filename': 'bad.pdf',
            },
            self.member_token,
        )
        self.assertTrue(is_error)
        self.assertIn('required', data['error'].lower())


class McpDistrictSessionCommitteeListTests(TestCase):
    """MCP list/get tools for committees, meetings, and sessions."""

    def setUp(self):
        self.client = Client()
        self.member = User.objects.create_user(
            username='list_member',
            email='list_member@example.com',
            password='memberpass123',
        )
        self.outsider = User.objects.create_user(
            username='list_outsider',
            email='list_outsider@example.com',
            password='outsiderpass123',
        )
        self.district = District.objects.create(
            name='List MCP District',
            code='LMD',
            description='Test',
            is_active=True,
        )
        self.other_district = District.objects.create(
            name='Other District',
            code='OTH',
            description='Other',
            is_active=True,
        )
        self.party = Party.objects.create(name='List Party', district=self.district, is_active=True)
        self.group = Group.objects.create(name='List Group', party=self.party, is_active=True)
        GroupMember.objects.create(user=self.member, group=self.group, is_active=True)
        self.council, _ = Council.objects.get_or_create(
            district=self.district,
            defaults={'name': 'List Council', 'is_active': True},
        )
        self.term = Term.objects.create(
            name='List Term',
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timedelta(days=365)).date(),
        )
        self.committee = Committee.objects.create(
            name='Kulturkommission',
            abbreviation='KK',
            council=self.council,
            is_active=True,
        )
        self.meeting_date = timezone.make_aware(datetime(2026, 10, 14, 18, 0))
        self.meeting = CommitteeMeeting.objects.create(
            committee=self.committee,
            title='KK 2026-10-14',
            scheduled_date=self.meeting_date,
            location='Rathaus',
            description='TOP 1: Budget',
            status='scheduled',
            is_active=True,
        )
        CommitteeMember.objects.create(
            committee=self.committee,
            user=self.member,
            role='member',
            is_active=True,
        )
        self.session = Session.objects.create(
            title='BV Sitzung',
            council=self.council,
            term=self.term,
            scheduled_date=self.meeting_date,
            location='Saal',
            is_active=True,
        )
        _, self.member_token = McpToken.create_token(self.member)
        _, self.outsider_token = McpToken.create_token(self.outsider)

    def _tool_call(self, name, arguments, token):
        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {'name': name, 'arguments': arguments},
        }
        response = self.client.post(
            reverse('mcp'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        result = body['result']
        text = result['content'][0]['text']
        return json.loads(text), result.get('isError', False)

    def test_list_committees_and_meetings_with_date_filter(self):
        data, is_error = self._tool_call(
            'list_committees',
            {'district_id': self.district.pk},
            self.member_token,
        )
        self.assertFalse(is_error)
        self.assertEqual(len(data['committees']), 1)
        self.assertEqual(data['committees'][0]['abbreviation'], 'KK')

        data, is_error = self._tool_call(
            'list_committee_meetings',
            {
                'district_id': self.district.pk,
                'committee_id': self.committee.pk,
                'from_date': '2026-10-01',
                'to_date': '2026-10-31',
            },
            self.member_token,
        )
        self.assertFalse(is_error)
        self.assertEqual(len(data['committee_meetings']), 1)
        meeting = data['committee_meetings'][0]
        self.assertEqual(meeting['id'], self.meeting.pk)
        self.assertEqual(meeting['committee']['name'], 'Kulturkommission')
        self.assertEqual(meeting['location'], 'Rathaus')

    def test_list_sessions_in_district(self):
        data, is_error = self._tool_call(
            'list_sessions',
            {
                'district_id': self.district.pk,
                'from_date': '2026-10-01',
                'to_date': '2026-10-31',
            },
            self.member_token,
        )
        self.assertFalse(is_error)
        self.assertEqual(len(data['sessions']), 1)
        self.assertEqual(data['sessions'][0]['id'], self.session.pk)

    def test_get_committee_meeting_includes_agenda_and_participants(self):
        data, is_error = self._tool_call(
            'get_committee_meeting',
            {'id': self.meeting.pk},
            self.member_token,
        )
        self.assertFalse(is_error)
        meeting = data['committee_meeting']
        self.assertEqual(meeting['agenda'], 'TOP 1: Budget')
        self.assertEqual(meeting['status'], 'scheduled')
        self.assertEqual(len(meeting['participants']), 1)
        self.assertEqual(meeting['participants'][0]['user_id'], self.member.pk)

    def test_outsider_cannot_list_foreign_district(self):
        data, is_error = self._tool_call(
            'list_committees',
            {'district_id': self.district.pk},
            self.outsider_token,
        )
        self.assertTrue(is_error)
        self.assertIn('access', data['error'].lower())


class McpAttachmentListDeleteTests(TestCase):
    """MCP list_attachments and delete_attachment tools."""

    PDF_BYTES = b'%PDF-1.4 list delete'

    def setUp(self):
        self.client = Client()
        self.member = User.objects.create_user(
            username='del_member',
            email='del_member@example.com',
            password='memberpass123',
        )
        self.outsider = User.objects.create_user(
            username='del_outsider',
            email='del_outsider@example.com',
            password='outsiderpass123',
        )
        self.district = District.objects.create(
            name='Del MCP District',
            code='DMD',
            description='Test',
            is_active=True,
        )
        self.party = Party.objects.create(name='Del Party', district=self.district, is_active=True)
        self.group = Group.objects.create(name='Del Group', party=self.party, is_active=True)
        GroupMember.objects.create(user=self.member, group=self.group, is_active=True)
        self.council, _ = Council.objects.get_or_create(
            district=self.district,
            defaults={'name': 'Del Council', 'is_active': True},
        )
        self.term = Term.objects.create(
            name='Del Term',
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timedelta(days=365)).date(),
        )
        self.session = Session.objects.create(
            title='Del Session',
            council=self.council,
            term=self.term,
            scheduled_date=timezone.now() + timedelta(days=2),
            is_active=True,
        )
        self.motion = Motion.objects.create(
            title='Del Motion',
            text='Body',
            session=self.session,
            group=self.group,
            submitted_by=self.member,
            status='draft',
        )
        _, self.member_token = McpToken.create_token(self.member)
        _, self.outsider_token = McpToken.create_token(self.outsider)
        self.pdf_base64 = base64.b64encode(self.PDF_BYTES).decode('ascii')

    def _tool_call(self, name, arguments, token):
        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {'name': name, 'arguments': arguments},
        }
        response = self.client.post(
            reverse('mcp'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        result = body['result']
        text = result['content'][0]['text']
        return json.loads(text), result.get('isError', False)

    def test_list_and_delete_motion_attachment(self):
        upload_data, upload_error = self._tool_call(
            'upload_motion_attachment',
            {
                'motion_id': self.motion.pk,
                'filename': 'listed.pdf',
                'content_base64': self.pdf_base64,
            },
            self.member_token,
        )
        self.assertFalse(upload_error)
        attachment_id = upload_data['attachment']['id']

        list_data, list_error = self._tool_call(
            'list_attachments',
            {'parent_type': 'motion', 'parent_id': self.motion.pk},
            self.member_token,
        )
        self.assertFalse(list_error)
        self.assertEqual(len(list_data['attachments']), 1)
        self.assertEqual(list_data['attachments'][0]['id'], attachment_id)

        denied, is_error = self._tool_call(
            'delete_attachment',
            {'parent_type': 'motion', 'attachment_id': attachment_id},
            self.outsider_token,
        )
        self.assertTrue(is_error)
        self.assertIn('permission', denied['error'].lower())
        self.assertTrue(MotionAttachment.objects.filter(pk=attachment_id).exists())

        deleted, is_error = self._tool_call(
            'delete_attachment',
            {'parent_type': 'motion', 'attachment_id': attachment_id},
            self.member_token,
        )
        self.assertFalse(is_error)
        self.assertTrue(deleted['deleted'])
        self.assertFalse(MotionAttachment.objects.filter(pk=attachment_id).exists())


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
