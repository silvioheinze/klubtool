"""
Comprehensive unit tests for access control across different user roles.

This test suite verifies that:
- Superusers have access to all views
- Regular users are denied access to admin views
- Users with role permissions can access permitted views
- Group leaders/deputy leaders can access group-specific views
- Group admins can manage their groups
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from user.models import Role
from local.models import Local, Council, Session, Term, Party, Committee
from group.models import Group, GroupMember, GroupMeeting
from motion.models import Motion, Inquiry

User = get_user_model()


class AccessControlTestCase(TestCase):
    """Base test case with common setup for access control tests"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Create users with different roles
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass123'
        )
        
        # Create role with permissions
        self.role_with_permissions = Role.objects.create(
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
            }
        )
        
        self.user_with_role = User.objects.create_user(
            username='editor',
            email='editor@example.com',
            password='editorpass123',
            role=self.role_with_permissions
        )
        
        # Create local, council, party, group for group-based tests
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description',
            is_active=True
        )
        
        self.council = self.local.council
        
        self.party = Party.objects.create(
            name='Test Party',
            local=self.local,
            is_active=True
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            party=self.party,
            is_active=True
        )
        
        # Create leader and deputy leader roles
        self.leader_role = Role.objects.get_or_create(name='Leader')[0]
        self.deputy_leader_role = Role.objects.get_or_create(name='Deputy Leader')[0]
        
        # Create group leader user
        self.group_leader = User.objects.create_user(
            username='leader',
            email='leader@example.com',
            password='leaderpass123'
        )
        
        # Add group leader to group with Leader role
        leader_membership = GroupMember.objects.create(
            user=self.group_leader,
            group=self.group,
            is_active=True
        )
        leader_membership.roles.add(self.leader_role)
        
        # Create group deputy leader user
        self.deputy_leader = User.objects.create_user(
            username='deputy',
            email='deputy@example.com',
            password='deputypass123'
        )
        
        # Add deputy leader to group with Deputy Leader role
        deputy_membership = GroupMember.objects.create(
            user=self.deputy_leader,
            group=self.group,
            is_active=True
        )
        deputy_membership.roles.add(self.deputy_leader_role)

        # Create plain group member (no Leader/Deputy/Admin) for testing member-level access
        self.plain_member_user = User.objects.create_user(
            username='member',
            email='member@example.com',
            password='memberpass123'
        )
        self.plain_member_membership = GroupMember.objects.create(
            user=self.plain_member_user,
            group=self.group,
            is_active=True
        )
        member_role = Role.objects.get_or_create(name='Member')[0]
        self.plain_member_membership.roles.add(member_role)
        
        # Create term and session for motion tests
        self.term = Term.objects.create(
            name='Test Term',
            start_date=timezone.now().date(),
            end_date=(timezone.now().date() + timedelta(days=365)),
            is_active=True
        )
        
        self.session = Session.objects.create(
            title='Test Session',
            council=self.council,
            term=self.term,
            scheduled_date=timezone.now() + timedelta(days=1),
            is_active=True
        )
        
        # Create a motion for testing
        self.motion = Motion.objects.create(
            title='Test Motion',
            text='Test motion text',
            session=self.session,
            group=self.group,
            submitted_by=self.regular_user,
            status='draft'
        )
        
        self.inquiry = Inquiry.objects.create(
            title='Test Inquiry',
            text='Test inquiry text',
            session=self.session,
            group=self.group,
            submitted_by=self.regular_user,
            status='draft'
        )


class UserManagementAccessTests(AccessControlTestCase):
    """Test access control for user management views"""
    
    def test_user_list_view_superuser_access(self):
        """Test that superuser can access user list"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('user-list'))
        self.assertEqual(response.status_code, 200)
    
    def test_user_list_view_regular_user_denied(self):
        """Test that regular user cannot access user list"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('user-list'))
        self.assertEqual(response.status_code, 403)
    
    def test_user_list_view_role_user_denied(self):
        """Test that user with role permissions cannot access user list (superuser only)"""
        self.client.login(username='editor', password='editorpass123')
        response = self.client.get(reverse('user-list'))
        self.assertEqual(response.status_code, 403)
    
    def test_user_edit_view_superuser_access(self):
        """Test that superuser can edit users"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('user-edit', kwargs={'user_id': self.regular_user.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_user_edit_view_regular_user_denied(self):
        """Test that regular user cannot edit users"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('user-edit', kwargs={'user_id': self.regular_user.pk}))
        self.assertEqual(response.status_code, 403)
    
    def test_user_edit_view_role_user_with_permission_access(self):
        """Test that user with user.edit permission can edit users"""
        self.client.login(username='editor', password='editorpass123')
        response = self.client.get(reverse('user-edit', kwargs={'user_id': self.regular_user.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_role_list_view_superuser_access(self):
        """Test that superuser can access role list"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('role-list'))
        self.assertEqual(response.status_code, 200)
    
    def test_role_list_view_regular_user_denied(self):
        """Test that regular user cannot access role list"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('role-list'))
        self.assertEqual(response.status_code, 403)
    
    def test_role_create_view_superuser_access(self):
        """Test that superuser can create roles"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('role-create'))
        self.assertEqual(response.status_code, 200)
    
    def test_role_create_view_regular_user_denied(self):
        """Test that regular user cannot create roles"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('role-create'))
        self.assertEqual(response.status_code, 403)
    
    def test_admin_settings_view_superuser_access(self):
        """Test that superuser can access admin settings"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('admin-settings'))
        self.assertEqual(response.status_code, 200)
    
    def test_admin_settings_view_regular_user_denied(self):
        """Test that regular user cannot access admin settings"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('admin-settings'))
        self.assertEqual(response.status_code, 403)


class MotionAccessTests(AccessControlTestCase):
    """Test access control for motion views"""
    
    def test_motion_list_view_superuser_access(self):
        """Test that superuser can view motion list"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('motion:motion-list'))
        self.assertEqual(response.status_code, 200)
    
    def test_motion_list_view_regular_user_denied(self):
        """Test that regular user without permission cannot view motion list"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('motion:motion-list'))
        self.assertEqual(response.status_code, 403)
    
    def test_motion_list_view_role_user_with_permission_access(self):
        """Test that user with motion.view permission can view motion list"""
        self.client.login(username='editor', password='editorpass123')
        response = self.client.get(reverse('motion:motion-list'))
        self.assertEqual(response.status_code, 200)
    
    def test_motion_detail_view_superuser_access(self):
        """Test that superuser can view motion detail"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('motion:motion-detail', kwargs={'pk': self.motion.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_motion_detail_view_regular_user_denied(self):
        """Test that regular user without permission cannot view motion detail"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('motion:motion-detail', kwargs={'pk': self.motion.pk}))
        self.assertEqual(response.status_code, 403)
    
    def test_motion_detail_view_role_user_with_permission_access(self):
        """Test that user with motion.view permission can view motion detail"""
        self.client.login(username='editor', password='editorpass123')
        response = self.client.get(reverse('motion:motion-detail', kwargs={'pk': self.motion.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_motion_create_view_superuser_access(self):
        """Test that superuser can create motions"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('motion:motion-create'))
        self.assertEqual(response.status_code, 200)
    
    def test_motion_create_view_regular_user_denied(self):
        """Test that regular user without permission cannot create motions"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('motion:motion-create'))
        self.assertEqual(response.status_code, 403)
    
    def test_motion_create_view_role_user_with_permission_access(self):
        """Test that user with motion.create permission can create motions"""
        self.client.login(username='editor', password='editorpass123')
        response = self.client.get(reverse('motion:motion-create'))
        self.assertEqual(response.status_code, 200)
    
    def test_motion_edit_view_superuser_access(self):
        """Test that superuser can edit motions"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('motion:motion-edit', kwargs={'pk': self.motion.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_motion_edit_view_regular_user_denied(self):
        """Test that regular user without permission cannot edit motions"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('motion:motion-edit', kwargs={'pk': self.motion.pk}))
        self.assertEqual(response.status_code, 403)
    
    def test_motion_edit_view_role_user_with_permission_access(self):
        """Test that user with motion.edit permission can edit motions"""
        self.client.login(username='editor', password='editorpass123')
        response = self.client.get(reverse('motion:motion-edit', kwargs={'pk': self.motion.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_motion_delete_view_superuser_access(self):
        """Test that superuser can delete motions"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('motion:motion-delete', kwargs={'pk': self.motion.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_motion_delete_view_regular_user_denied(self):
        """Test that regular user cannot delete motions (unless they submitted it)"""
        self.client.login(username='regular', password='regularpass123')
        # Regular user submitted the motion, so they might have access
        # But the view requires motion.delete permission or superuser
        # Let's test with a different user
        other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='otherpass123'
        )
        self.client.login(username='other', password='otherpass123')
        response = self.client.get(reverse('motion:motion-delete', kwargs={'pk': self.motion.pk}))
        self.assertEqual(response.status_code, 403)

    def test_motion_list_view_group_member_access(self):
        """Test that group member can view motion list (their group's motions)"""
        self.client.login(username='member', password='memberpass123')
        response = self.client.get(reverse('motion:motion-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.motion.title)

    def test_motion_detail_view_group_member_access(self):
        """Test that group member can view motion detail of their group"""
        self.client.login(username='member', password='memberpass123')
        response = self.client.get(reverse('motion:motion-detail', kwargs={'pk': self.motion.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.motion.title)

    def test_motion_edit_view_group_member_access(self):
        """Test that group member can edit motions of their group"""
        self.client.login(username='member', password='memberpass123')
        response = self.client.get(reverse('motion:motion-edit', kwargs={'pk': self.motion.pk}))
        self.assertEqual(response.status_code, 200)

    def test_motion_attach_view_group_member_access(self):
        """Test that group member can attach files to motions of their group"""
        self.client.login(username='member', password='memberpass123')
        response = self.client.get(reverse('motion:motion-attach', kwargs={'pk': self.motion.pk}))
        self.assertEqual(response.status_code, 200)


class InquiryAccessTests(AccessControlTestCase):
    """Test access control for inquiry views"""
    
    def test_inquiry_list_view_superuser_access(self):
        """Test that superuser can view inquiry list"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('inquiry:inquiry-list'))
        self.assertEqual(response.status_code, 200)
    
    def test_inquiry_list_view_regular_user_denied(self):
        """Test that regular user without permission cannot view inquiry list"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('inquiry:inquiry-list'))
        self.assertEqual(response.status_code, 403)
    
    def test_inquiry_list_view_role_user_with_permission_access(self):
        """Test that user with motion.view permission can view inquiry list"""
        self.client.login(username='editor', password='editorpass123')
        response = self.client.get(reverse('inquiry:inquiry-list'))
        self.assertEqual(response.status_code, 200)
    
    def test_inquiry_detail_view_superuser_access(self):
        """Test that superuser can view inquiry detail"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('inquiry:inquiry-detail', kwargs={'pk': self.inquiry.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_inquiry_detail_view_regular_user_denied(self):
        """Test that regular user without permission cannot view inquiry detail"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('inquiry:inquiry-detail', kwargs={'pk': self.inquiry.pk}))
        self.assertEqual(response.status_code, 403)
    
    def test_inquiry_detail_view_role_user_with_permission_access(self):
        """Test that user with motion.view permission can view inquiry detail"""
        self.client.login(username='editor', password='editorpass123')
        response = self.client.get(reverse('inquiry:inquiry-detail', kwargs={'pk': self.inquiry.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_inquiry_create_view_superuser_access(self):
        """Test that superuser can create inquiries"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('inquiry:inquiry-create'))
        self.assertEqual(response.status_code, 200)
    
    def test_inquiry_create_view_regular_user_denied(self):
        """Test that regular user without permission cannot create inquiries"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('inquiry:inquiry-create'))
        self.assertEqual(response.status_code, 403)
    
    def test_inquiry_create_view_role_user_with_permission_access(self):
        """Test that user with motion.create permission can create inquiries"""
        self.client.login(username='editor', password='editorpass123')
        response = self.client.get(reverse('inquiry:inquiry-create'))
        self.assertEqual(response.status_code, 200)
    
    def test_inquiry_edit_view_superuser_access(self):
        """Test that superuser can edit inquiries"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('inquiry:inquiry-edit', kwargs={'pk': self.inquiry.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_inquiry_edit_view_regular_user_denied(self):
        """Test that regular user without permission cannot edit inquiries"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('inquiry:inquiry-edit', kwargs={'pk': self.inquiry.pk}))
        self.assertEqual(response.status_code, 403)
    
    def test_inquiry_edit_view_role_user_with_permission_access(self):
        """Test that user with motion.edit permission can edit inquiries"""
        self.client.login(username='editor', password='editorpass123')
        response = self.client.get(reverse('inquiry:inquiry-edit', kwargs={'pk': self.inquiry.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_inquiry_delete_view_superuser_access(self):
        """Test that superuser can delete inquiries"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('inquiry:inquiry-delete', kwargs={'pk': self.inquiry.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_inquiry_delete_view_regular_user_denied(self):
        """Test that regular user cannot delete inquiries (unless they submitted it)"""
        # Test with a different user
        other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='otherpass123'
        )
        self.client.login(username='other', password='otherpass123')
        response = self.client.get(reverse('inquiry:inquiry-delete', kwargs={'pk': self.inquiry.pk}))
        self.assertEqual(response.status_code, 403)

    def test_inquiry_list_view_group_member_access(self):
        """Test that group member can view inquiry list (their group's inquiries)"""
        self.client.login(username='member', password='memberpass123')
        response = self.client.get(reverse('inquiry:inquiry-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.inquiry.title)

    def test_inquiry_detail_view_group_member_access(self):
        """Test that group member can view inquiry detail of their group"""
        self.client.login(username='member', password='memberpass123')
        response = self.client.get(reverse('inquiry:inquiry-detail', kwargs={'pk': self.inquiry.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.inquiry.title)

    def test_inquiry_edit_view_group_member_access(self):
        """Test that group member can edit inquiries of their group"""
        self.client.login(username='member', password='memberpass123')
        response = self.client.get(reverse('inquiry:inquiry-edit', kwargs={'pk': self.inquiry.pk}))
        self.assertEqual(response.status_code, 200)

    def test_inquiry_attach_view_group_member_access(self):
        """Test that group member can attach files to inquiries of their group"""
        self.client.login(username='member', password='memberpass123')
        response = self.client.get(reverse('inquiry:inquiry-attach', kwargs={'pk': self.inquiry.pk}))
        self.assertEqual(response.status_code, 200)

    def test_inquiry_create_view_group_member_access(self):
        """Test that group member can create inquiries for session of their council"""
        self.client.login(username='member', password='memberpass123')
        response = self.client.get(
            reverse('inquiry:inquiry-create') + f'?session={self.session.pk}'
        )
        self.assertEqual(response.status_code, 200)


class GroupAccessTests(AccessControlTestCase):
    """Test access control for group views"""
    
    def test_group_list_view_superuser_access(self):
        """Test that superuser can view group list"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('group:group-list'))
        self.assertEqual(response.status_code, 200)
    
    def test_group_list_view_regular_user_denied(self):
        """Test that regular user without permission cannot view group list"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('group:group-list'))
        self.assertEqual(response.status_code, 403)
    
    def test_group_list_view_role_user_with_permission_access(self):
        """Test that user with group.view permission can view group list"""
        self.client.login(username='editor', password='editorpass123')
        response = self.client.get(reverse('group:group-list'))
        self.assertEqual(response.status_code, 200)
    
    def test_group_detail_view_superuser_access(self):
        """Test that superuser can view group detail"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('group:group-detail', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_group_detail_view_regular_user_denied(self):
        """Test that regular user without permission cannot view group detail"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('group:group-detail', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 403)
    
    def test_group_detail_view_role_user_with_permission_access(self):
        """Test that user with group.view permission can view group detail"""
        self.client.login(username='editor', password='editorpass123')
        response = self.client.get(reverse('group:group-detail', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_group_detail_view_group_leader_access(self):
        """Test that group leader can view their group detail"""
        self.client.login(username='leader', password='leaderpass123')
        response = self.client.get(reverse('group:group-detail', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_group_detail_view_deputy_leader_access(self):
        """Test that deputy leader can view their group detail"""
        self.client.login(username='deputy', password='deputypass123')
        response = self.client.get(reverse('group:group-detail', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 200)

    def test_group_detail_view_plain_member_access(self):
        """Test that plain group member (no leader/admin role) can view their group detail"""
        self.client.login(username='member', password='memberpass123')
        response = self.client.get(reverse('group:group-detail', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.group.name)
    
    def test_group_create_view_superuser_access(self):
        """Test that superuser can create groups"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('group:group-create'))
        self.assertEqual(response.status_code, 200)
    
    def test_group_create_view_regular_user_denied(self):
        """Test that regular user without permission cannot create groups"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('group:group-create'))
        self.assertEqual(response.status_code, 403)
    
    def test_group_create_view_role_user_with_permission_access(self):
        """Test that user with group.create permission can create groups"""
        self.client.login(username='editor', password='editorpass123')
        response = self.client.get(reverse('group:group-create'))
        self.assertEqual(response.status_code, 200)
    
    def test_group_edit_view_superuser_access(self):
        """Test that superuser can edit groups"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('group:group-edit', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_group_edit_view_regular_user_denied(self):
        """Test that regular user without permission cannot edit groups"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('group:group-edit', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 403)
    
    def test_group_edit_view_role_user_with_permission_access(self):
        """Test that user with group.edit permission can edit groups"""
        self.client.login(username='editor', password='editorpass123')
        response = self.client.get(reverse('group:group-edit', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_group_edit_view_group_leader_access(self):
        """Test that group leader can edit their group"""
        self.client.login(username='leader', password='leaderpass123')
        response = self.client.get(reverse('group:group-edit', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_group_edit_view_deputy_leader_access(self):
        """Test that deputy leader can edit their group"""
        self.client.login(username='deputy', password='deputypass123')
        response = self.client.get(reverse('group:group-edit', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_group_delete_view_superuser_access(self):
        """Test that superuser can delete groups"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('group:group-delete', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_group_delete_view_regular_user_denied(self):
        """Test that regular user cannot delete groups"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('group:group-delete', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 403)
    
    def test_group_delete_view_group_leader_denied(self):
        """Test that group leader cannot delete groups (requires group.delete permission)"""
        self.client.login(username='leader', password='leaderpass123')
        response = self.client.get(reverse('group:group-delete', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 403)

    def test_member_detail_view_superuser_access(self):
        """Test that superuser can view member detail"""
        leader_membership = GroupMember.objects.get(user=self.group_leader, group=self.group)
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('group:member-detail', kwargs={'pk': leader_membership.pk}))
        self.assertEqual(response.status_code, 200)

    def test_member_detail_view_role_user_with_group_view_access(self):
        """Test that user with group.view permission can view member detail"""
        leader_membership = GroupMember.objects.get(user=self.group_leader, group=self.group)
        self.client.login(username='editor', password='editorpass123')
        response = self.client.get(reverse('group:member-detail', kwargs={'pk': leader_membership.pk}))
        self.assertEqual(response.status_code, 200)

    def test_member_detail_view_regular_user_denied(self):
        """Test that regular user cannot view member detail"""
        leader_membership = GroupMember.objects.get(user=self.group_leader, group=self.group)
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('group:member-detail', kwargs={'pk': leader_membership.pk}))
        self.assertEqual(response.status_code, 403)

    def test_member_detail_view_group_leader_denied(self):
        """Test that group leader cannot view member detail (requires group.view permission)"""
        leader_membership = GroupMember.objects.get(user=self.group_leader, group=self.group)
        self.client.login(username='leader', password='leaderpass123')
        response = self.client.get(reverse('group:member-detail', kwargs={'pk': leader_membership.pk}))
        self.assertEqual(response.status_code, 403)


class LocalAccessTests(AccessControlTestCase):
    """Test access control for local/council/session views"""
    
    def test_local_list_view_superuser_access(self):
        """Test that superuser can view local list"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:local-list'))
        self.assertEqual(response.status_code, 200)
    
    def test_local_list_view_regular_user_denied(self):
        """Test that regular user cannot view local list"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('local:local-list'))
        self.assertEqual(response.status_code, 403)
    
    def test_local_list_view_role_user_denied(self):
        """Test that user with role permissions cannot view local list (superuser only)"""
        self.client.login(username='editor', password='editorpass123')
        response = self.client.get(reverse('local:local-list'))
        self.assertEqual(response.status_code, 403)
    
    def test_session_detail_view_superuser_access(self):
        """Test that superuser can view session detail"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:session-detail', kwargs={'pk': self.session.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_session_detail_view_regular_user_denied(self):
        """Test that regular user cannot view session detail"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('local:session-detail', kwargs={'pk': self.session.pk}))
        self.assertEqual(response.status_code, 403)
    
    def test_session_create_view_superuser_access(self):
        """Test that superuser can create sessions"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:session-create'))
        self.assertEqual(response.status_code, 200)
    
    def test_session_create_view_regular_user_denied(self):
        """Test that regular user cannot create sessions"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('local:session-create'))
        self.assertEqual(response.status_code, 403)
    
    def test_council_detail_view_superuser_access(self):
        """Test that superuser can view council detail"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:council-detail', kwargs={'pk': self.council.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_council_detail_view_regular_user_denied(self):
        """Test that regular user cannot view council detail"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('local:council-detail', kwargs={'pk': self.council.pk}))
        self.assertEqual(response.status_code, 403)

    def test_council_detail_view_group_member_access(self):
        """Test that group member can view council detail for council connected to their group"""
        # group_leader is member of self.group; self.group.party.local.council == self.council
        self.client.login(username='leader', password='leaderpass123')
        response = self.client.get(reverse('local:council-detail', kwargs={'pk': self.council.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.council.name)

    def test_session_detail_view_group_member_access(self):
        """Test that group member can view session detail for session of council connected to their group"""
        self.client.login(username='leader', password='leaderpass123')
        response = self.client.get(reverse('local:session-detail', kwargs={'pk': self.session.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.session.title)

    def test_local_detail_view_superuser_access(self):
        """Test that superuser can view local detail"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:local-detail', kwargs={'pk': self.local.pk}))
        self.assertEqual(response.status_code, 200)

    def test_local_detail_view_regular_user_denied(self):
        """Test that regular user cannot view local detail"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('local:local-detail', kwargs={'pk': self.local.pk}))
        self.assertEqual(response.status_code, 403)

    def test_local_detail_view_group_member_access(self):
        """Test that group member can view local detail for local connected to their group (via party)"""
        self.client.login(username='leader', password='leaderpass123')
        response = self.client.get(reverse('local:local-detail', kwargs={'pk': self.local.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.local.name)


class GroupMeetingAccessTests(AccessControlTestCase):
    """Test access control for group meeting views"""
    
    def setUp(self):
        """Set up additional test data for meetings"""
        super().setUp()
        
        # Create a group meeting
        self.meeting = GroupMeeting.objects.create(
            group=self.group,
            title='Test Meeting',
            scheduled_date=timezone.now() + timedelta(days=1),
            created_by=self.superuser
        )
    
    def test_meeting_detail_view_superuser_access(self):
        """Test that superuser can view meeting detail"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('group:meeting-detail', kwargs={'pk': self.meeting.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_meeting_detail_view_regular_user_denied(self):
        """Test that regular user cannot view meeting detail"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('group:meeting-detail', kwargs={'pk': self.meeting.pk}))
        self.assertEqual(response.status_code, 403)
    
    def test_meeting_detail_view_group_leader_access(self):
        """Test that group leader can view meeting detail"""
        self.client.login(username='leader', password='leaderpass123')
        response = self.client.get(reverse('group:meeting-detail', kwargs={'pk': self.meeting.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_meeting_detail_view_deputy_leader_access(self):
        """Test that deputy leader can view meeting detail"""
        self.client.login(username='deputy', password='deputypass123')
        response = self.client.get(reverse('group:meeting-detail', kwargs={'pk': self.meeting.pk}))
        self.assertEqual(response.status_code, 200)

    def test_meeting_detail_view_plain_member_access(self):
        """Test that plain group member can view meeting detail"""
        self.client.login(username='member', password='memberpass123')
        response = self.client.get(reverse('group:meeting-detail', kwargs={'pk': self.meeting.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.meeting.title)
    
    def test_meeting_create_view_superuser_access(self):
        """Test that superuser can create meetings"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('group:meeting-create'))
        self.assertEqual(response.status_code, 200)
    
    def test_meeting_create_view_regular_user_denied(self):
        """Test that regular user cannot create meetings"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('group:meeting-create'))
        self.assertEqual(response.status_code, 403)
    
    def test_meeting_edit_view_superuser_access(self):
        """Test that superuser can edit meetings"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('group:meeting-edit', kwargs={'pk': self.meeting.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_meeting_edit_view_regular_user_denied(self):
        """Test that regular user cannot edit meetings"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('group:meeting-edit', kwargs={'pk': self.meeting.pk}))
        self.assertEqual(response.status_code, 403)
    
    def test_meeting_edit_view_group_leader_access(self):
        """Test that group leader can edit meetings"""
        self.client.login(username='leader', password='leaderpass123')
        response = self.client.get(reverse('group:meeting-edit', kwargs={'pk': self.meeting.pk}))
        self.assertEqual(response.status_code, 200)

    def test_meeting_edit_view_plain_member_denied(self):
        """Test that plain group member cannot edit meetings"""
        self.client.login(username='member', password='memberpass123')
        response = self.client.get(reverse('group:meeting-edit', kwargs={'pk': self.meeting.pk}))
        self.assertEqual(response.status_code, 403)
    
    def test_meeting_delete_view_superuser_access(self):
        """Test that superuser can delete meetings"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('group:meeting-delete', kwargs={'pk': self.meeting.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_meeting_delete_view_regular_user_denied(self):
        """Test that regular user cannot delete meetings"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(reverse('group:meeting-delete', kwargs={'pk': self.meeting.pk}))
        self.assertEqual(response.status_code, 403)
    
    def test_meeting_delete_view_group_leader_access(self):
        """Test that group leader can delete meetings"""
        self.client.login(username='leader', password='leaderpass123')
        response = self.client.get(reverse('group:meeting-delete', kwargs={'pk': self.meeting.pk}))
        self.assertEqual(response.status_code, 200)

    def test_meeting_delete_view_plain_member_denied(self):
        """Test that plain group member cannot delete meetings"""
        self.client.login(username='member', password='memberpass123')
        response = self.client.get(reverse('group:meeting-delete', kwargs={'pk': self.meeting.pk}))
        self.assertEqual(response.status_code, 403)


class AnonymousUserAccessTests(AccessControlTestCase):
    """Test that anonymous users are denied access to protected views"""
    
    def test_user_list_view_anonymous_denied(self):
        """Test that anonymous user cannot access user list"""
        response = self.client.get(reverse('user-list'))
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/user/settings/', response.url)
    
    def test_motion_list_view_anonymous_denied(self):
        """Test that anonymous user cannot access motion list"""
        response = self.client.get(reverse('motion:motion-list'))
        # Should redirect to login
        self.assertEqual(response.status_code, 302)

    def test_inquiry_list_view_anonymous_denied(self):
        """Test that anonymous user cannot access inquiry list"""
        response = self.client.get(reverse('inquiry:inquiry-list'))
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
    
    def test_group_list_view_anonymous_denied(self):
        """Test that anonymous user cannot access group list"""
        response = self.client.get(reverse('group:group-list'))
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
    
    def test_local_list_view_anonymous_denied(self):
        """Test that anonymous user cannot access local list"""
        response = self.client.get(reverse('local:local-list'))
        # Should redirect to login
        self.assertEqual(response.status_code, 302)

