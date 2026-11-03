"""Tests for token-based committee meeting attachment PUT uploads."""

import json
import time
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.cache import caches
from django.test import Client, TestCase, override_settings
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
)
from district.upload_validation import UPLOAD_PUT_MAX_BYTES
from group.models import Group, GroupMember, Role
from user.models import McpToken

User = get_user_model()

UPLOAD_TEST_CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'klubtool-default-test',
    },
    'upload_tokens': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'upload-tokens-test',
    },
}


@override_settings(CACHES=UPLOAD_TEST_CACHES)
class CommitteeMeetingAttachmentPutUploadTests(TestCase):
    PDF_BYTES = b'%PDF-1.4 put upload test'

    def setUp(self):
        caches['upload_tokens'].clear()
        self.client = Client()
        self.committee_member_user = User.objects.create_user(
            username='put_cm_member',
            email='put_cm_member@example.com',
            password='memberpass123',
        )
        self.group_leader = User.objects.create_user(
            username='put_cm_leader',
            email='put_cm_leader@example.com',
            password='leaderpass123',
        )
        self.outsider = User.objects.create_user(
            username='put_cm_outsider',
            email='put_cm_outsider@example.com',
            password='outsiderpass123',
        )
        self.superuser = User.objects.create_superuser(
            username='put_cm_super',
            email='put_cm_super@example.com',
            password='superpass123',
        )
        self.district = District.objects.create(
            name='PUT District',
            code='PUTD',
            description='Test',
            is_active=True,
        )
        self.party = Party.objects.create(
            name='PUT Party',
            district=self.district,
            is_active=True,
        )
        self.group = Group.objects.create(
            name='PUT Group',
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
            defaults={'name': 'PUT Council', 'is_active': True},
        )
        self.committee = Committee.objects.create(
            name='PUT Committee',
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
            title='PUT Meeting',
            scheduled_date=timezone.now() + timedelta(days=2),
            status='scheduled',
            is_active=True,
        )
        _, self.leader_token = McpToken.create_token(self.group_leader)
        _, self.superuser_token = McpToken.create_token(self.superuser)

    def _mcp_create_upload_url(self, token, **extra):
        args = {
            'committee_meeting_id': self.meeting.pk,
            'filename': 'upload.pdf',
            'file_type': 'agenda',
        }
        args.update(extra)
        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {'name': 'create_committee_meeting_upload_url', 'arguments': args},
        }
        response = self.client.post(
            reverse('mcp'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        text = body['result']['content'][0]['text']
        data = json.loads(text)
        is_error = body['result'].get('isError', False)
        return data, is_error

    def _upload_path_from_url(self, upload_url: str) -> str:
        prefix = 'https://testserver'
        self.assertTrue(upload_url.startswith(prefix))
        return upload_url[len(prefix):]

    def test_put_upload_creates_attachment(self):
        data, is_error = self._mcp_create_upload_url(self.superuser_token)
        self.assertFalse(is_error)
        self.assertIn('upload_url', data)
        self.assertEqual(data['max_bytes'], UPLOAD_PUT_MAX_BYTES)
        path = self._upload_path_from_url(data['upload_url'])
        response = self.client.put(
            path,
            data=self.PDF_BYTES,
            content_type='application/pdf',
        )
        self.assertEqual(response.status_code, 201, response.content)
        payload = response.json()
        self.assertEqual(payload['filename'], 'upload.pdf')
        self.assertEqual(payload['file_size'], len(self.PDF_BYTES))
        attachment = CommitteeMeetingAttachment.objects.get(pk=payload['id'])
        self.assertEqual(attachment.committee_meeting_id, self.meeting.pk)

    def test_second_put_returns_409(self):
        data, _ = self._mcp_create_upload_url(self.superuser_token)
        path = self._upload_path_from_url(data['upload_url'])
        first = self.client.put(path, data=self.PDF_BYTES, content_type='application/pdf')
        self.assertEqual(first.status_code, 201)
        second = self.client.put(path, data=self.PDF_BYTES, content_type='application/pdf')
        self.assertEqual(second.status_code, 409)

    def test_tampered_token_rejected(self):
        data, _ = self._mcp_create_upload_url(self.superuser_token)
        path = self._upload_path_from_url(data['upload_url']) + 'x'
        response = self.client.put(path, data=self.PDF_BYTES, content_type='application/pdf')
        self.assertEqual(response.status_code, 403)

    @override_settings(ATTACHMENT_UPLOAD_TOKEN_TTL=1)
    def test_expired_token_rejected(self):
        data, _ = self._mcp_create_upload_url(self.superuser_token, filename='late.pdf')
        path = self._upload_path_from_url(data['upload_url'])
        time.sleep(1.1)
        response = self.client.put(path, data=self.PDF_BYTES, content_type='application/pdf')
        self.assertEqual(response.status_code, 403)

    def test_invalid_pdf_content_rejected(self):
        data, _ = self._mcp_create_upload_url(self.superuser_token, filename='bad.pdf')
        path = self._upload_path_from_url(data['upload_url'])
        response = self.client.put(path, data=b'not a pdf', content_type='application/pdf')
        self.assertEqual(response.status_code, 400)

    def test_oversized_body_rejected(self):
        data, _ = self._mcp_create_upload_url(self.superuser_token, filename='big.pdf')
        path = self._upload_path_from_url(data['upload_url'])
        too_large_body = b'%PDF' + (b'0' * (UPLOAD_PUT_MAX_BYTES - 3))
        self.assertGreater(len(too_large_body), UPLOAD_PUT_MAX_BYTES)
        response = self.client.put(
            path,
            data=too_large_body,
            content_type='application/pdf',
        )
        self.assertEqual(response.status_code, 413)

    def test_permission_revoked_before_put(self):
        data, _ = self._mcp_create_upload_url(self.leader_token)
        path = self._upload_path_from_url(data['upload_url'])
        membership = GroupMember.objects.get(user=self.group_leader, group=self.group)
        membership.roles.clear()
        response = self.client.put(path, data=self.PDF_BYTES, content_type='application/pdf')
        self.assertEqual(response.status_code, 403)

    def test_invitation_upload_sets_meeting_invited(self):
        data, _ = self._mcp_create_upload_url(
            self.superuser_token,
            filename='inv.pdf',
            file_type='invitation',
        )
        path = self._upload_path_from_url(data['upload_url'])
        response = self.client.put(path, data=self.PDF_BYTES, content_type='application/pdf')
        self.assertEqual(response.status_code, 201)
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.status, 'invited')

    def test_minutes_upload_sets_meeting_completed(self):
        data, _ = self._mcp_create_upload_url(
            self.superuser_token,
            filename='minutes.pdf',
            file_type='minutes',
        )
        path = self._upload_path_from_url(data['upload_url'])
        response = self.client.put(path, data=self.PDF_BYTES, content_type='application/pdf')
        self.assertEqual(response.status_code, 201)
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.status, 'completed')


@override_settings(CACHES=UPLOAD_TEST_CACHES)
class DistrictEventAttachmentPutUploadTests(TestCase):
    PDF_BYTES = b'%PDF-1.4 district event put'

    def setUp(self):
        caches['upload_tokens'].clear()
        self.client = Client()
        self.manager = User.objects.create_user(
            username='put_event_manager',
            email='put_event_manager@example.com',
            password='managerpass123',
        )
        self.superuser = User.objects.create_superuser(
            username='put_event_super',
            email='put_event_super@example.com',
            password='superpass123',
        )
        self.district = District.objects.create(
            name='PUT Event District',
            code='PED',
            description='Test',
            is_active=True,
        )
        self.party = Party.objects.create(name='PUT Event Party', district=self.district, is_active=True)
        self.group = Group.objects.create(name='PUT Event Group', party=self.party, is_active=True)
        leader_role = Role.objects.get_or_create(name='Leader', defaults={'is_active': True})[0]
        membership = GroupMember.objects.create(user=self.manager, group=self.group, is_active=True)
        membership.roles.add(leader_role)
        self.event = DistrictEvent.objects.create(
            title='PUT Event',
            district=self.district,
            scheduled_date=timezone.now() + timedelta(days=3),
            created_by=self.manager,
        )
        _, self.manager_token = McpToken.create_token(self.manager)
        _, self.superuser_token = McpToken.create_token(self.superuser)

    def _mcp_create_upload_url(self, token, **extra):
        args = {
            'event_id': self.event.pk,
            'filename': 'upload.pdf',
            'file_type': 'agenda',
        }
        args.update(extra)
        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {'name': 'create_district_event_upload_url', 'arguments': args},
        }
        response = self.client.post(
            reverse('mcp'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        text = body['result']['content'][0]['text']
        data = json.loads(text)
        is_error = body['result'].get('isError', False)
        return data, is_error

    def _upload_path_from_url(self, upload_url: str) -> str:
        prefix = 'https://testserver'
        self.assertTrue(upload_url.startswith(prefix))
        return upload_url[len(prefix):]

    def test_put_upload_creates_attachment(self):
        data, is_error = self._mcp_create_upload_url(self.superuser_token)
        self.assertFalse(is_error)
        path = self._upload_path_from_url(data['upload_url'])
        response = self.client.put(
            path,
            data=self.PDF_BYTES,
            content_type='application/pdf',
        )
        self.assertEqual(response.status_code, 201, response.content)
        payload = response.json()
        self.assertEqual(payload['filename'], 'upload.pdf')
        attachment = DistrictEventAttachment.objects.get(pk=payload['id'])
        self.assertEqual(attachment.event_id, self.event.pk)

    def test_second_put_returns_409(self):
        data, _ = self._mcp_create_upload_url(self.superuser_token)
        path = self._upload_path_from_url(data['upload_url'])
        first = self.client.put(path, data=self.PDF_BYTES, content_type='application/pdf')
        self.assertEqual(first.status_code, 201)
        second = self.client.put(path, data=self.PDF_BYTES, content_type='application/pdf')
        self.assertEqual(second.status_code, 409)

    def test_tampered_token_rejected(self):
        data, _ = self._mcp_create_upload_url(self.superuser_token)
        path = self._upload_path_from_url(data['upload_url']) + 'x'
        response = self.client.put(path, data=self.PDF_BYTES, content_type='application/pdf')
        self.assertEqual(response.status_code, 403)

    def test_permission_revoked_before_put(self):
        data, _ = self._mcp_create_upload_url(self.manager_token)
        path = self._upload_path_from_url(data['upload_url'])
        membership = GroupMember.objects.get(user=self.manager, group=self.group)
        membership.roles.clear()
        response = self.client.put(path, data=self.PDF_BYTES, content_type='application/pdf')
        self.assertEqual(response.status_code, 403)
