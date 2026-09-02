"""
Comprehensive unit tests for access control across different user roles.

This test suite verifies that:
- Superusers have access to all views
- Regular users are denied access to admin views
- Users with role permissions can access permitted views
- Group leaders/deputy leaders can access group-specific views
- Group admins can manage their groups
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from district.models import District, Session, Term, Party
from group.models import Group, GroupMember, GroupMeeting
from motion.models import Motion, Inquiry
from user.models import Role

User = get_user_model()


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AccessControlTestCase(TestCase):
    """Base test case with common setup for access control tests."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
        )

        cls.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass123',
        )

        cls.role_with_permissions = Role.objects.create(
            name='Editor Role',
            description='Role with various permissions',
            is_active=True,
            permissions={
                'permissions': [
                    'user.edit',
                    'motion.view',
                    'motion.create',
                    'motion.edit',
                    'group.view',
                    'group.create',
                    'group.edit',
                ]
            },
        )

        cls.user_with_role = User.objects.create_user(
            username='editor',
            email='editor@example.com',
            password='editorpass123',
            role=cls.role_with_permissions,
        )

        cls.other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='otherpass123',
        )

        cls.district = District.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description',
            is_active=True,
        )

        cls.council = cls.district.council

        cls.party = Party.objects.create(
            name='Test Party',
            district=cls.district,
            is_active=True,
        )

        cls.group = Group.objects.create(
            name='Test Group',
            party=cls.party,
            is_active=True,
        )

        cls.leader_role = Role.objects.get_or_create(name='Leader')[0]
        cls.deputy_leader_role = Role.objects.get_or_create(name='Deputy Leader')[0]

        cls.group_leader = User.objects.create_user(
            username='leader',
            email='leader@example.com',
            password='leaderpass123',
        )

        cls.leader_membership = GroupMember.objects.create(
            user=cls.group_leader,
            group=cls.group,
            is_active=True,
        )
        cls.leader_membership.roles.add(cls.leader_role)

        cls.deputy_leader = User.objects.create_user(
            username='deputy',
            email='deputy@example.com',
            password='deputypass123',
        )

        deputy_membership = GroupMember.objects.create(
            user=cls.deputy_leader,
            group=cls.group,
            is_active=True,
        )
        deputy_membership.roles.add(cls.deputy_leader_role)

        cls.plain_member_user = User.objects.create_user(
            username='member',
            email='member@example.com',
            password='memberpass123',
        )
        cls.plain_member_membership = GroupMember.objects.create(
            user=cls.plain_member_user,
            group=cls.group,
            is_active=True,
        )
        member_role = Role.objects.get_or_create(name='Member')[0]
        cls.plain_member_membership.roles.add(member_role)

        cls.term = Term.objects.create(
            name='Test Term',
            start_date=timezone.now().date(),
            end_date=(timezone.now().date() + timedelta(days=365)),
            is_active=True,
        )

        cls.session = Session.objects.create(
            title='Test Session',
            council=cls.council,
            term=cls.term,
            scheduled_date=timezone.now() + timedelta(days=1),
            is_active=True,
        )

        cls.motion = Motion.objects.create(
            title='Test Motion',
            text='Test motion text',
            session=cls.session,
            group=cls.group,
            submitted_by=cls.regular_user,
            status='draft',
        )

        cls.inquiry = Inquiry.objects.create(
            title='Test Inquiry',
            text='Test inquiry text',
            session=cls.session,
            group=cls.group,
            submitted_by=cls.regular_user,
            status='draft',
        )

    def assert_get(self, user, url, status, *, contains=None, content_type=None):
        if user is None:
            self.client.logout()
        else:
            self.client.force_login(user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status)
        if contains is not None:
            self.assertContains(response, contains)
        if content_type is not None:
            self.assertEqual(response['Content-Type'], content_type)
        return response

    def run_access_cases(self, url, cases):
        for case in cases:
            user = case[0]
            status = case[1]
            contains = case[2] if len(case) > 2 else None
            content_type = case[3] if len(case) > 3 else None
            label = user.username if user else 'anonymous'
            with self.subTest(user=label, url=url, status=status):
                self.assert_get(user, url, status, contains=contains, content_type=content_type)


class UserManagementAccessTests(AccessControlTestCase):
    """Test access control for user management views."""

    def test_user_list_access(self):
        self.run_access_cases(reverse('user-list'), [
            (self.superuser, 200),
            (self.regular_user, 403),
            (self.user_with_role, 403),
        ])

    def test_user_edit_access(self):
        url = reverse('user-edit', kwargs={'user_id': self.regular_user.pk})
        self.run_access_cases(url, [
            (self.superuser, 200),
            (self.regular_user, 403),
            (self.user_with_role, 200),
        ])

    def test_role_list_access(self):
        self.run_access_cases(reverse('role-list'), [
            (self.superuser, 200),
            (self.regular_user, 403),
        ])

    def test_role_create_access(self):
        self.run_access_cases(reverse('role-create'), [
            (self.superuser, 200),
            (self.regular_user, 403),
        ])

    def test_admin_settings_access(self):
        self.run_access_cases(reverse('admin-settings'), [
            (self.superuser, 200),
            (self.regular_user, 403),
        ])


class MotionAccessTests(AccessControlTestCase):
    """Test access control for motion views."""

    def test_motion_list_access(self):
        self.run_access_cases(reverse('motion:motion-list'), [
            (self.superuser, 200),
            (self.regular_user, 403),
            (self.user_with_role, 200),
            (self.plain_member_user, 200, self.motion.title),
        ])

    def test_motion_detail_access(self):
        url = reverse('motion:motion-detail', kwargs={'pk': self.motion.pk})
        self.run_access_cases(url, [
            (self.superuser, 200),
            (self.regular_user, 403),
            (self.user_with_role, 200),
            (self.plain_member_user, 200, self.motion.title),
        ])

    def test_motion_create_access(self):
        self.run_access_cases(reverse('motion:motion-create'), [
            (self.superuser, 200),
            (self.regular_user, 403),
            (self.user_with_role, 200),
        ])

    def test_motion_edit_access(self):
        url = reverse('motion:motion-edit', kwargs={'pk': self.motion.pk})
        self.run_access_cases(url, [
            (self.superuser, 200),
            (self.regular_user, 403),
            (self.user_with_role, 200),
            (self.plain_member_user, 200),
        ])

    def test_motion_delete_access(self):
        url = reverse('motion:motion-delete', kwargs={'pk': self.motion.pk})
        self.run_access_cases(url, [
            (self.superuser, 200),
            (self.other_user, 403),
        ])

    def test_motion_attach_access(self):
        url = reverse('motion:motion-attach', kwargs={'pk': self.motion.pk})
        self.run_access_cases(url, [
            (self.plain_member_user, 200),
        ])


class InquiryAccessTests(AccessControlTestCase):
    """Test access control for inquiry views."""

    def test_inquiry_list_access(self):
        self.run_access_cases(reverse('inquiry:inquiry-list'), [
            (self.superuser, 200),
            (self.regular_user, 403),
            (self.user_with_role, 200),
            (self.plain_member_user, 200, self.inquiry.title),
        ])

    def test_inquiry_detail_access(self):
        url = reverse('inquiry:inquiry-detail', kwargs={'pk': self.inquiry.pk})
        self.run_access_cases(url, [
            (self.superuser, 200),
            (self.regular_user, 403),
            (self.user_with_role, 200),
            (self.plain_member_user, 200, self.inquiry.title),
        ])

    def test_inquiry_create_access(self):
        self.run_access_cases(reverse('inquiry:inquiry-create'), [
            (self.superuser, 200),
            (self.regular_user, 403),
            (self.user_with_role, 200),
        ])

    def test_inquiry_create_group_member_with_session(self):
        url = reverse('inquiry:inquiry-create') + f'?session={self.session.pk}'
        self.run_access_cases(url, [
            (self.plain_member_user, 200),
        ])

    def test_inquiry_edit_access(self):
        url = reverse('inquiry:inquiry-edit', kwargs={'pk': self.inquiry.pk})
        self.run_access_cases(url, [
            (self.superuser, 200),
            (self.regular_user, 403),
            (self.user_with_role, 200),
            (self.plain_member_user, 200),
        ])

    def test_inquiry_delete_access(self):
        url = reverse('inquiry:inquiry-delete', kwargs={'pk': self.inquiry.pk})
        self.run_access_cases(url, [
            (self.superuser, 200),
            (self.other_user, 403),
        ])

    def test_inquiry_attach_access(self):
        url = reverse('inquiry:inquiry-attach', kwargs={'pk': self.inquiry.pk})
        self.run_access_cases(url, [
            (self.plain_member_user, 200),
        ])

    def test_inquiry_export_pdf_access(self):
        url = reverse('inquiry:inquiry-export-pdf', kwargs={'pk': self.inquiry.pk})
        self.run_access_cases(url, [
            (self.superuser, 200, None, 'application/pdf'),
            (self.regular_user, 403),
            (self.plain_member_user, 200, None, 'application/pdf'),
        ])

    def test_inquiry_export_pdf_anonymous_redirects(self):
        url = reverse('inquiry:inquiry-export-pdf', kwargs={'pk': self.inquiry.pk})
        self.run_access_cases(url, [
            (None, 302),
        ])


class GroupAccessTests(AccessControlTestCase):
    """Test access control for group views."""

    def test_group_list_access(self):
        self.run_access_cases(reverse('group:group-list'), [
            (self.superuser, 200),
            (self.regular_user, 403),
            (self.user_with_role, 200),
        ])

    def test_group_detail_access(self):
        url = reverse('group:group-detail', kwargs={'pk': self.group.pk})
        self.run_access_cases(url, [
            (self.superuser, 200),
            (self.regular_user, 403),
            (self.user_with_role, 200),
            (self.group_leader, 200),
            (self.deputy_leader, 200),
            (self.plain_member_user, 200, self.group.name),
        ])

    def test_group_create_access(self):
        self.run_access_cases(reverse('group:group-create'), [
            (self.superuser, 200),
            (self.regular_user, 403),
            (self.user_with_role, 200),
        ])

    def test_group_edit_access(self):
        url = reverse('group:group-edit', kwargs={'pk': self.group.pk})
        self.run_access_cases(url, [
            (self.superuser, 200),
            (self.regular_user, 403),
            (self.user_with_role, 200),
            (self.group_leader, 200),
            (self.deputy_leader, 200),
        ])

    def test_group_delete_access(self):
        url = reverse('group:group-delete', kwargs={'pk': self.group.pk})
        self.run_access_cases(url, [
            (self.superuser, 200),
            (self.regular_user, 403),
            (self.group_leader, 403),
        ])

    def test_member_detail_access(self):
        url = reverse('group:member-detail', kwargs={'pk': self.leader_membership.pk})
        self.run_access_cases(url, [
            (self.superuser, 200),
            (self.user_with_role, 200),
            (self.regular_user, 403),
            (self.group_leader, 403),
        ])


class DistrictAccessTests(AccessControlTestCase):
    """Test access control for local/council/session views."""

    def test_district_list_access(self):
        self.run_access_cases(reverse('district:district-list'), [
            (self.superuser, 200),
            (self.regular_user, 403),
            (self.user_with_role, 403),
        ])

    def test_session_detail_access(self):
        url = reverse('district:session-detail', kwargs={'pk': self.session.pk})
        self.run_access_cases(url, [
            (self.superuser, 200),
            (self.regular_user, 403),
            (self.group_leader, 200, self.session.title),
        ])

    def test_session_create_access(self):
        self.run_access_cases(reverse('district:session-create'), [
            (self.superuser, 200),
            (self.regular_user, 403),
        ])

    def test_council_detail_access(self):
        url = reverse('district:council-detail', kwargs={'pk': self.council.pk})
        self.run_access_cases(url, [
            (self.superuser, 200),
            (self.regular_user, 403),
            (self.group_leader, 200, self.council.name),
        ])

    def test_district_detail_access(self):
        url = reverse('district:district-detail', kwargs={'pk': self.district.pk})
        self.run_access_cases(url, [
            (self.superuser, 200),
            (self.regular_user, 403),
            (self.group_leader, 200, self.district.name),
        ])


class GroupMeetingAccessTests(AccessControlTestCase):
    """Test access control for group meeting views."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.meeting = GroupMeeting.objects.create(
            group=cls.group,
            title='Test Meeting',
            scheduled_date=timezone.now() + timedelta(days=1),
            created_by=cls.superuser,
        )

    def test_meeting_detail_access(self):
        url = reverse('group:meeting-detail', kwargs={'pk': self.meeting.pk})
        self.run_access_cases(url, [
            (self.superuser, 200),
            (self.regular_user, 403),
            (self.group_leader, 200),
            (self.deputy_leader, 200),
            (self.plain_member_user, 200, self.meeting.title),
        ])

    def test_meeting_create_access(self):
        self.run_access_cases(reverse('group:meeting-create'), [
            (self.superuser, 200),
            (self.regular_user, 403),
        ])

    def test_meeting_edit_access(self):
        url = reverse('group:meeting-edit', kwargs={'pk': self.meeting.pk})
        self.run_access_cases(url, [
            (self.superuser, 200),
            (self.regular_user, 403),
            (self.group_leader, 200),
            (self.plain_member_user, 403),
        ])

    def test_meeting_delete_access(self):
        url = reverse('group:meeting-delete', kwargs={'pk': self.meeting.pk})
        self.run_access_cases(url, [
            (self.superuser, 200),
            (self.regular_user, 403),
            (self.group_leader, 200),
            (self.plain_member_user, 403),
        ])


class AnonymousUserAccessTests(AccessControlTestCase):
    """Test that anonymous users are denied access to protected views."""

    def test_protected_views_anonymous_denied(self):
        cases = [
            (reverse('user-list'), 302, '/user/settings/'),
            (reverse('motion:motion-list'), 302, None),
            (reverse('inquiry:inquiry-list'), 302, None),
            (reverse('group:group-list'), 302, None),
            (reverse('district:district-list'), 302, None),
        ]
        for url, status, redirect_fragment in cases:
            with self.subTest(url=url):
                response = self.assert_get(None, url, status)
                if redirect_fragment:
                    self.assertIn(redirect_fragment, response.url)
