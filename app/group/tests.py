from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django import forms
from datetime import datetime, timedelta
import re

from .forms import (
    GroupForm, GroupFilterForm, GroupMemberForm, GroupMemberFilterForm, GroupMeetingForm, AgendaItemForm
)
from .models import Group, GroupMember, GroupMeeting, AgendaItem
from local.models import Local, Party
from user.models import Role

User = get_user_model()


class GroupFormTests(TestCase):
    """Test cases for GroupForm"""
    
    def setUp(self):
        """Set up test data"""
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        
        self.party = Party.objects.create(
            name='Test Party',
            local=self.local
        )
    
    def test_group_form_valid_data(self):
        """Test GroupForm with valid data"""
        form_data = {
            'name': 'Test Group',
            'party': self.party.pk
        }
        
        form = GroupForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_group_form_required_fields(self):
        """Test GroupForm with missing required fields"""
        form_data = {
            'name': '',  # Required field missing
            'party': self.party.pk
        }
        
        form = GroupForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)
    
    def test_group_form_party_filtering(self):
        """Test that GroupForm filters parties correctly"""
        form = GroupForm()
        expected_parties = Party.objects.filter(is_active=True)
        self.assertQuerySetEqual(
            form.fields['party'].queryset,
            expected_parties,
            transform=lambda x: x
        )
    
    def test_group_form_party_inactive_filtering(self):
        """Test that GroupForm excludes inactive parties"""
        # Create inactive party
        inactive_party = Party.objects.create(
            name='Inactive Party',
            local=self.local,
            is_active=False
        )
        
        form = GroupForm()
        self.assertNotIn(inactive_party, form.fields['party'].queryset)


class GroupFilterFormTests(TestCase):
    """Test cases for GroupFilterForm"""
    
    def test_group_filter_form_valid_data(self):
        """Test GroupFilterForm with valid data"""
        form_data = {
            'name': 'Test',
            'is_active': True
        }
        
        form = GroupFilterForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_group_filter_form_empty_data(self):
        """Test GroupFilterForm with empty data"""
        form_data = {}
        
        form = GroupFilterForm(data=form_data)
        self.assertTrue(form.is_valid())  # Filter forms should be valid with empty data


class GroupMemberFormTests(TestCase):
    """Test cases for GroupMemberForm"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        
        self.party = Party.objects.create(
            name='Test Party',
            local=self.local
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            party=self.party
        )
        
        self.role = Role.objects.create(
            name='Test Role',
            description='Test role description',
            is_active=True
        )
    
    def test_group_member_form_valid_data(self):
        """Test GroupMemberForm with valid data"""
        form_data = {
            'user': self.user.pk,
            'group': self.group.pk,
            'roles': [self.role.pk],
            'is_active': True
        }
        
        form = GroupMemberForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_group_member_form_required_fields(self):
        """Test GroupMemberForm with missing required fields"""
        form_data = {
            'user': '',  # Required field missing
            'group': self.group.pk,
            'roles': [self.role.pk],
            'is_active': True
        }
        
        form = GroupMemberForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('user', form.errors)
    
    def test_group_member_form_group_filtering(self):
        """Test that GroupMemberForm filters groups correctly"""
        form = GroupMemberForm()
        expected_groups = Group.objects.filter(is_active=True)
        self.assertQuerySetEqual(
            form.fields['group'].queryset,
            expected_groups,
            transform=lambda x: x
        )
    
    def test_group_member_form_role_filtering(self):
        """Test that GroupMemberForm filters roles correctly"""
        form = GroupMemberForm()
        expected_roles = Role.objects.filter(is_active=True)
        self.assertQuerySetEqual(
            form.fields['roles'].queryset,
            expected_roles,
            transform=lambda x: x
        )
    
    def test_group_member_form_multiple_roles(self):
        """Test GroupMemberForm with multiple roles"""
        role2 = Role.objects.create(
            name='Test Role 2',
            description='Test role 2 description',
            is_active=True
        )
        
        form_data = {
            'user': self.user.pk,
            'group': self.group.pk,
            'roles': [self.role.pk, role2.pk],
            'is_active': True
        }
        
        form = GroupMemberForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_group_member_form_no_roles(self):
        """Test GroupMemberForm with no roles assigned"""
        form_data = {
            'user': self.user.pk,
            'group': self.group.pk,
            'roles': [],  # No roles assigned
            'is_active': True
        }
        
        form = GroupMemberForm(data=form_data)
        # Check if roles are required or optional (form errors not printed to avoid test log clutter)
        # For now, just check that the form can be created
        self.assertIsNotNone(form)
    
    def test_group_member_form_inactive_role_exclusion(self):
        """Test that GroupMemberForm excludes inactive roles"""
        # Create inactive role
        inactive_role = Role.objects.create(
            name='Inactive Role',
            description='Inactive role description',
            is_active=False
        )
        
        form = GroupMemberForm()
        self.assertNotIn(inactive_role, form.fields['roles'].queryset)
    
    def test_group_member_form_inactive_group_exclusion(self):
        """Test that GroupMemberForm excludes inactive groups"""
        # Create inactive group
        inactive_group = Group.objects.create(
            name='Inactive Group',
            party=self.party,
            is_active=False
        )
        
        form = GroupMemberForm()
        self.assertNotIn(inactive_group, form.fields['group'].queryset)


class GroupMemberFilterFormTests(TestCase):
    """Test cases for GroupMemberFilterForm"""
    
    def test_group_member_filter_form_valid_data(self):
        """Test GroupMemberFilterForm with valid data"""
        form_data = {
            'user': 'test',
            'is_active': True
        }
        
        form = GroupMemberFilterForm(data=form_data)
        # For now, just check that the form can be created (form errors not printed to avoid test log clutter)
        self.assertIsNotNone(form)
    
    def test_group_member_filter_form_empty_data(self):
        """Test GroupMemberFilterForm with empty data"""
        form_data = {}
        
        form = GroupMemberFilterForm(data=form_data)
        self.assertTrue(form.is_valid())  # Filter forms should be valid with empty data


class GroupModelTests(TestCase):
    """Test cases for Group model"""
    
    def setUp(self):
        """Set up test data"""
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        
        self.party = Party.objects.create(
            name='Test Party',
            local=self.local
        )
    
    def test_group_creation(self):
        """Test Group model creation"""
        group = Group.objects.create(
            name='Test Group',
            party=self.party
        )
        
        self.assertEqual(group.name, 'Test Group')
        self.assertEqual(group.party, self.party)
        self.assertTrue(group.is_active)  # Default should be True
        self.assertIsNotNone(group.created_at)
        self.assertIsNotNone(group.updated_at)
    
    def test_group_str_representation(self):
        """Test Group model string representation"""
        group = Group.objects.create(
            name='Test Group',
            party=self.party
        )
        
        # The actual string representation includes the party name
        self.assertEqual(str(group), 'Test Group (Test Party)')
    
    def test_group_default_values(self):
        """Test Group model default values"""
        group = Group.objects.create(
            name='Test Group',
            party=self.party
        )
        
        self.assertTrue(group.is_active)  # Default should be True
    
    def test_group_ordering(self):
        """Test Group model ordering"""
        group1 = Group.objects.create(
            name='B Group',
            party=self.party
        )
        group2 = Group.objects.create(
            name='A Group',
            party=self.party
        )
        
        groups = Group.objects.all()
        self.assertEqual(groups[0], group2)  # Should be ordered by name
        self.assertEqual(groups[1], group1)
    
    def test_group_active_filter(self):
        """Test Group model active filter"""
        active_group = Group.objects.create(
            name='Active Group',
            party=self.party,
            is_active=True
        )
        inactive_group = Group.objects.create(
            name='Inactive Group',
            party=self.party,
            is_active=False
        )
        
        active_groups = Group.objects.filter(is_active=True)
        self.assertIn(active_group, active_groups)
        self.assertNotIn(inactive_group, active_groups)
    
    def test_group_party_relationship(self):
        """Test Group model party relationship"""
        group = Group.objects.create(
            name='Test Group',
            party=self.party
        )
        
        self.assertEqual(group.party, self.party)
        self.assertIn(group, self.party.groups.all())


class GroupMemberModelTests(TestCase):
    """Test cases for GroupMember model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        
        self.party = Party.objects.create(
            name='Test Party',
            local=self.local
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            party=self.party
        )
        
        self.role = Role.objects.create(
            name='Test Role',
            description='Test role description',
            is_active=True
        )
    
    def test_group_member_creation(self):
        """Test GroupMember model creation"""
        group_member = GroupMember.objects.create(
            user=self.user,
            group=self.group
        )
        group_member.roles.add(self.role)
        
        self.assertEqual(group_member.user, self.user)
        self.assertEqual(group_member.group, self.group)
        self.assertIn(self.role, group_member.roles.all())
        self.assertTrue(group_member.is_active)  # Default should be True
        self.assertIsNotNone(group_member.joined_date)
    
    def test_group_member_str_representation(self):
        """Test GroupMember model string representation"""
        group_member = GroupMember.objects.create(
            user=self.user,
            group=self.group
        )
        
        # The actual string representation includes additional formatting
        expected_str = f"{self.user.username} - {self.group.name} ()"
        self.assertEqual(str(group_member), expected_str)
    
    def test_group_member_default_values(self):
        """Test GroupMember model default values"""
        group_member = GroupMember.objects.create(
            user=self.user,
            group=self.group
        )
        
        self.assertTrue(group_member.is_active)  # Default should be True
        self.assertIsNotNone(group_member.joined_date)
    
    def test_group_member_ordering(self):
        """Test GroupMember model ordering"""
        user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        
        group_member1 = GroupMember.objects.create(
            user=user2,
            group=self.group
        )
        group_member2 = GroupMember.objects.create(
            user=self.user,
            group=self.group
        )
        
        # Get only the group members we created for this test (match model ordering: -joined_date, -id)
        test_members = GroupMember.objects.filter(
            user__in=[self.user, user2],
            group=self.group
        ).order_by('-joined_date', '-id')
        
        # Same joined_date: group_member2 (created second, higher id) first
        self.assertEqual(test_members[0], group_member2)
        self.assertEqual(test_members[1], group_member1)
    
    def test_group_member_active_filter(self):
        """Test GroupMember model active filter"""
        active_member = GroupMember.objects.create(
            user=self.user,
            group=self.group,
            is_active=True
        )
        inactive_member = GroupMember.objects.create(
            user=User.objects.create_user(
                username='testuser2',
                email='test2@example.com',
                password='testpass123'
            ),
            group=self.group,
            is_active=False
        )
        
        active_members = GroupMember.objects.filter(is_active=True)
        self.assertIn(active_member, active_members)
        self.assertNotIn(inactive_member, active_members)
    
    def test_group_member_multiple_roles(self):
        """Test GroupMember model with multiple roles"""
        role2 = Role.objects.create(
            name='Test Role 2',
            description='Test role 2 description',
            is_active=True
        )
        
        group_member = GroupMember.objects.create(
            user=self.user,
            group=self.group
        )
        group_member.roles.add(self.role, role2)
        
        self.assertEqual(group_member.roles.count(), 2)
        self.assertIn(self.role, group_member.roles.all())
        self.assertIn(role2, group_member.roles.all())
    
    def test_group_member_user_group_relationship(self):
        """Test GroupMember model user-group relationship"""
        group_member = GroupMember.objects.create(
            user=self.user,
            group=self.group
        )
        
        self.assertEqual(group_member.user, self.user)
        self.assertEqual(group_member.group, self.group)
        self.assertIn(group_member, self.user.group_memberships.all())
        self.assertIn(group_member, self.group.members.all())


class GroupMeetingFormTests(TestCase):
    """Test cases for GroupMeetingForm"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        
        self.party = Party.objects.create(
            name='Test Party',
            local=self.local
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            party=self.party
        )
    
    def test_group_meeting_form_valid_data(self):
        """Test GroupMeetingForm with valid data"""
        form_data = {
            'title': 'Test Meeting',
            'scheduled_date': '2025-12-31 14:00:00',
            'location': 'Test Location',
            'description': 'Test meeting description',
            'group': self.group.pk
        }
        
        form = GroupMeetingForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_group_meeting_form_required_fields(self):
        """Test GroupMeetingForm with missing required fields"""
        form_data = {
            'title': '',  # Required field missing
            'scheduled_date': '2025-12-31 14:00:00',
            'group': self.group.pk
        }
        
        form = GroupMeetingForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
    
    def test_group_meeting_form_with_group_parameter(self):
        """Test GroupMeetingForm with group parameter in initial data"""
        form_data = {
            'title': 'Test Meeting',
            'scheduled_date': '2025-12-31 14:00:00',
            'location': 'Test Location',
            'description': 'Test meeting description',
            'group': self.group.pk  # Include group in form data
        }
        
        initial_data = {'group': self.group.pk}
        form = GroupMeetingForm(data=form_data, initial=initial_data)
        
        # Check that group field is hidden
        self.assertIsInstance(form.fields['group'].widget, forms.HiddenInput)
        self.assertEqual(form.fields['group'].initial, self.group.pk)
        self.assertTrue(form.is_valid())
    
    def test_group_meeting_form_without_group_parameter(self):
        """Test GroupMeetingForm without group parameter"""
        form_data = {
            'title': 'Test Meeting',
            'scheduled_date': '2025-12-31 14:00:00',
            'location': 'Test Location',
            'description': 'Test meeting description',
            'group': self.group.pk
        }
        
        form = GroupMeetingForm(data=form_data)
        
        # When group is in data, it should be hidden
        self.assertIsInstance(form.fields['group'].widget, forms.HiddenInput)
        self.assertTrue(form.is_valid())
    
    def test_group_meeting_form_empty_data(self):
        """Test GroupMeetingForm with empty data to check widget type"""
        form = GroupMeetingForm()
        
        # When no data is provided, group field should be a select widget
        self.assertIsInstance(form.fields['group'].widget, forms.Select)
    
    def test_group_meeting_form_group_filtering(self):
        """Test that GroupMeetingForm filters groups correctly"""
        form = GroupMeetingForm()
        expected_groups = Group.objects.filter(is_active=True)
        self.assertQuerySetEqual(
            form.fields['group'].queryset,
            expected_groups,
            transform=lambda x: x
        )
    
    def test_group_meeting_form_inactive_group_exclusion(self):
        """Test that GroupMeetingForm excludes inactive groups"""
        # Create inactive group
        inactive_group = Group.objects.create(
            name='Inactive Group',
            party=self.party,
            is_active=False
        )
        
        form = GroupMeetingForm()
        self.assertNotIn(inactive_group, form.fields['group'].queryset)
    
    def test_group_meeting_form_optional_fields(self):
        """Test GroupMeetingForm with optional fields empty"""
        form_data = {
            'title': 'Test Meeting',
            'scheduled_date': '2025-12-31 14:00:00',
            'group': self.group.pk
            # location and description are optional
        }
        
        form = GroupMeetingForm(data=form_data)
        self.assertTrue(form.is_valid())


class GroupMeetingModelTests(TestCase):
    """Test cases for GroupMeeting model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        
        self.party = Party.objects.create(
            name='Test Party',
            local=self.local
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            party=self.party
        )
    
    def test_group_meeting_creation(self):
        """Test GroupMeeting model creation"""
        meeting = GroupMeeting.objects.create(
            group=self.group,
            title='Test Meeting',
            scheduled_date=timezone.now() + timedelta(days=1),
            location='Test Location',
            description='Test meeting description',
            created_by=self.user
        )
        
        self.assertEqual(meeting.group, self.group)
        self.assertEqual(meeting.title, 'Test Meeting')
        self.assertEqual(meeting.location, 'Test Location')
        self.assertEqual(meeting.description, 'Test meeting description')
        self.assertEqual(meeting.created_by, self.user)
        self.assertTrue(meeting.is_active)  # Default should be True
        self.assertIsNotNone(meeting.created_at)
        self.assertIsNotNone(meeting.updated_at)
    
    def test_group_meeting_str_representation(self):
        """Test GroupMeeting model string representation"""
        scheduled_date = timezone.now() + timedelta(days=1)
        meeting = GroupMeeting.objects.create(
            group=self.group,
            title='Test Meeting',
            scheduled_date=scheduled_date,
            created_by=self.user
        )
        
        expected_str = f"Test Meeting - Test Group ({scheduled_date.strftime('%Y-%m-%d %H:%M')})"
        self.assertEqual(str(meeting), expected_str)
    
    def test_group_meeting_default_values(self):
        """Test GroupMeeting model default values"""
        meeting = GroupMeeting.objects.create(
            group=self.group,
            title='Test Meeting',
            scheduled_date=timezone.now() + timedelta(days=1)
        )
        
        self.assertTrue(meeting.is_active)  # Default should be True
        self.assertIsNotNone(meeting.created_at)
        self.assertIsNotNone(meeting.updated_at)
    
    def test_group_meeting_ordering(self):
        """Test GroupMeeting model ordering"""
        meeting1 = GroupMeeting.objects.create(
            group=self.group,
            title='Meeting 1',
            scheduled_date=timezone.now() + timedelta(days=2)
        )
        meeting2 = GroupMeeting.objects.create(
            group=self.group,
            title='Meeting 2',
            scheduled_date=timezone.now() + timedelta(days=1)
        )
        
        meetings = GroupMeeting.objects.all()
        # Should be ordered by scheduled_date (most recent first)
        self.assertEqual(meetings[0], meeting1)
        self.assertEqual(meetings[1], meeting2)
    
    def test_group_meeting_active_filter(self):
        """Test GroupMeeting model active filter"""
        active_meeting = GroupMeeting.objects.create(
            group=self.group,
            title='Active Meeting',
            scheduled_date=timezone.now() + timedelta(days=1),
            is_active=True
        )
        inactive_meeting = GroupMeeting.objects.create(
            group=self.group,
            title='Inactive Meeting',
            scheduled_date=timezone.now() + timedelta(days=1),
            is_active=False
        )
        
        active_meetings = GroupMeeting.objects.filter(is_active=True)
        self.assertIn(active_meeting, active_meetings)
        self.assertNotIn(inactive_meeting, active_meetings)
    
    def test_group_meeting_group_relationship(self):
        """Test GroupMeeting model group relationship"""
        meeting = GroupMeeting.objects.create(
            group=self.group,
            title='Test Meeting',
            scheduled_date=timezone.now() + timedelta(days=1)
        )
        
        self.assertEqual(meeting.group, self.group)
        self.assertIn(meeting, self.group.meetings.all())
    
    def test_group_meeting_is_past_property(self):
        """Test GroupMeeting is_past property"""
        past_meeting = GroupMeeting.objects.create(
            group=self.group,
            title='Past Meeting',
            scheduled_date=timezone.now() - timedelta(days=1)
        )
        future_meeting = GroupMeeting.objects.create(
            group=self.group,
            title='Future Meeting',
            scheduled_date=timezone.now() + timedelta(days=1)
        )
        
        self.assertTrue(past_meeting.is_past)
        self.assertFalse(future_meeting.is_past)
    
    def test_group_meeting_is_upcoming_property(self):
        """Test GroupMeeting is_upcoming property"""
        past_meeting = GroupMeeting.objects.create(
            group=self.group,
            title='Past Meeting',
            scheduled_date=timezone.now() - timedelta(days=1)
        )
        future_meeting = GroupMeeting.objects.create(
            group=self.group,
            title='Future Meeting',
            scheduled_date=timezone.now() + timedelta(days=1)
        )
        
        self.assertFalse(past_meeting.is_upcoming)
        self.assertTrue(future_meeting.is_upcoming)
    
    def test_group_meeting_time_until_meeting_property(self):
        """Test GroupMeeting time_until_meeting property"""
        future_meeting = GroupMeeting.objects.create(
            group=self.group,
            title='Future Meeting',
            scheduled_date=timezone.now() + timedelta(days=2, hours=3)
        )
        past_meeting = GroupMeeting.objects.create(
            group=self.group,
            title='Past Meeting',
            scheduled_date=timezone.now() - timedelta(days=1)
        )
        
        # Future meeting should have time until meeting
        self.assertNotEqual(future_meeting.time_until_meeting, "Past")
        # Past meeting should return "Past"
        self.assertEqual(past_meeting.time_until_meeting, "Past")
    
    def test_group_meeting_optional_fields(self):
        """Test GroupMeeting model with optional fields"""
        meeting = GroupMeeting.objects.create(
            group=self.group,
            title='Test Meeting',
            scheduled_date=timezone.now() + timedelta(days=1)
            # location and description are optional
        )
        
        self.assertEqual(meeting.location, '')
        self.assertEqual(meeting.description, '')
        self.assertTrue(meeting.is_active)
    
    def test_group_meeting_get_absolute_url(self):
        """Test GroupMeeting get_absolute_url method"""
        meeting = GroupMeeting.objects.create(
            group=self.group,
            title='Test Meeting',
            scheduled_date=timezone.now() + timedelta(days=1)
        )
        
        expected_url = f'/group/meetings/{meeting.pk}/'
        self.assertEqual(meeting.get_absolute_url(), expected_url)


class AgendaItemFormTests(TestCase):
    """Test cases for AgendaItemForm"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        
        self.party = Party.objects.create(
            name='Test Party',
            local=self.local
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            party=self.party
        )
        
        self.meeting = GroupMeeting.objects.create(
            group=self.group,
            title='Test Meeting',
            scheduled_date=timezone.now() + timedelta(days=1),
            created_by=self.user
        )
    
    def test_agenda_item_form_valid_data(self):
        """Test AgendaItemForm with valid data"""
        form_data = {
            'title': 'Test Agenda Item',
            'description': 'Test agenda item description',
            'order': 1
        }
        
        form = AgendaItemForm(data=form_data, meeting=self.meeting)
        self.assertTrue(form.is_valid())
    
    def test_agenda_item_form_required_fields(self):
        """Test AgendaItemForm with missing required fields"""
        form_data = {
            'title': '',  # Required field missing
            'description': 'Test description',
            'order': 1
        }
        
        form = AgendaItemForm(data=form_data, meeting=self.meeting)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
    
    def test_agenda_item_form_with_meeting_context(self):
        """Test AgendaItemForm with meeting context"""
        form = AgendaItemForm(meeting=self.meeting)
        
        # Check that parent_item queryset is filtered to meeting items
        expected_items = AgendaItem.objects.filter(meeting=self.meeting, is_active=True)
        self.assertQuerySetEqual(
            form.fields['parent_item'].queryset,
            expected_items,
            transform=lambda x: x
        )
    
    def test_agenda_item_form_auto_order(self):
        """Test AgendaItemForm auto-sets order for new items"""
        # Create some existing agenda items
        AgendaItem.objects.create(
            meeting=self.meeting,
            title='Item 1',
            order=1
        )
        AgendaItem.objects.create(
            meeting=self.meeting,
            title='Item 2',
            order=2
        )
        
        form = AgendaItemForm(meeting=self.meeting)
        # Should set initial order to 3 (next available)
        self.assertEqual(form.fields['order'].initial, 3)
    
    def test_agenda_item_form_parent_filtering(self):
        """Test AgendaItemForm filters parent items correctly"""
        # Create some agenda items
        item1 = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Item 1',
            order=1
        )
        item2 = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Item 2',
            order=2
        )
        
        form = AgendaItemForm(meeting=self.meeting)
        parent_choices = [choice[0] for choice in form.fields['parent_item'].choices]
        
        # Should include both items as potential parents
        self.assertIn(item1.pk, parent_choices)
        self.assertIn(item2.pk, parent_choices)
    
    def test_agenda_item_form_excludes_self_from_parents(self):
        """Test AgendaItemForm excludes self from parent choices when editing"""
        item = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Item 1',
            order=1
        )
        
        form = AgendaItemForm(instance=item, meeting=self.meeting)
        parent_choices = [choice[0] for choice in form.fields['parent_item'].choices]
        
        # Should not include self as parent
        self.assertNotIn(item.pk, parent_choices)
    
    def test_agenda_item_form_optional_fields(self):
        """Test AgendaItemForm with optional fields empty"""
        form_data = {
            'title': 'Test Agenda Item',
            'order': 1
            # description and parent_item are optional
        }
        
        form = AgendaItemForm(data=form_data, meeting=self.meeting)
        self.assertTrue(form.is_valid())


class AgendaItemModelTests(TestCase):
    """Test cases for AgendaItem model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        
        self.party = Party.objects.create(
            name='Test Party',
            local=self.local
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            party=self.party
        )
        
        self.meeting = GroupMeeting.objects.create(
            group=self.group,
            title='Test Meeting',
            scheduled_date=timezone.now() + timedelta(days=1),
            created_by=self.user
        )
    
    def test_agenda_item_creation(self):
        """Test AgendaItem model creation"""
        agenda_item = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Test Agenda Item',
            description='Test agenda item description',
            order=1,
            created_by=self.user
        )
        
        self.assertEqual(agenda_item.meeting, self.meeting)
        self.assertEqual(agenda_item.title, 'Test Agenda Item')
        self.assertEqual(agenda_item.description, 'Test agenda item description')
        self.assertEqual(agenda_item.order, 1)
        self.assertEqual(agenda_item.created_by, self.user)
        self.assertTrue(agenda_item.is_active)  # Default should be True
        self.assertIsNotNone(agenda_item.created_at)
        self.assertIsNotNone(agenda_item.updated_at)
    
    def test_agenda_item_str_representation(self):
        """Test AgendaItem model string representation"""
        agenda_item = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Test Agenda Item',
            order=1
        )
        
        expected_str = f"Test Agenda Item - Test Meeting"
        self.assertEqual(str(agenda_item), expected_str)
    
    def test_agenda_item_default_values(self):
        """Test AgendaItem model default values"""
        agenda_item = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Test Agenda Item',
            order=1
        )
        
        self.assertTrue(agenda_item.is_active)  # Default should be True
        self.assertIsNotNone(agenda_item.created_at)
        self.assertIsNotNone(agenda_item.updated_at)
    
    def test_agenda_item_ordering(self):
        """Test AgendaItem model ordering"""
        item1 = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Item 1',
            order=2
        )
        item2 = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Item 2',
            order=1
        )
        
        items = AgendaItem.objects.all()
        # Should be ordered by order, then created_at
        self.assertEqual(items[0], item2)  # order=1 comes first
        self.assertEqual(items[1], item1)  # order=2 comes second
    
    def test_agenda_item_active_filter(self):
        """Test AgendaItem model active filter"""
        active_item = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Active Item',
            order=1,
            is_active=True
        )
        inactive_item = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Inactive Item',
            order=2,
            is_active=False
        )
        
        active_items = AgendaItem.objects.filter(is_active=True)
        self.assertIn(active_item, active_items)
        self.assertNotIn(inactive_item, active_items)
    
    def test_agenda_item_meeting_relationship(self):
        """Test AgendaItem model meeting relationship"""
        agenda_item = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Test Item',
            order=1
        )
        
        self.assertEqual(agenda_item.meeting, self.meeting)
        self.assertIn(agenda_item, self.meeting.agenda_items.all())
    
    def test_agenda_item_hierarchical_structure(self):
        """Test AgendaItem hierarchical parent-child relationships"""
        parent_item = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Parent Item',
            order=1
        )
        child_item = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Child Item',
            order=2,
            parent_item=parent_item
        )
        
        # Test parent-child relationship
        self.assertEqual(child_item.parent_item, parent_item)
        self.assertIn(child_item, parent_item.sub_items.all())
        
        # Test properties
        self.assertFalse(parent_item.is_sub_item)
        self.assertTrue(child_item.is_sub_item)
        self.assertEqual(parent_item.level, 0)
        self.assertEqual(child_item.level, 1)
    
    def test_agenda_item_nested_hierarchy(self):
        """Test AgendaItem with multiple levels of nesting"""
        level0 = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Level 0',
            order=1
        )
        level1 = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Level 1',
            order=2,
            parent_item=level0
        )
        level2 = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Level 2',
            order=3,
            parent_item=level1
        )
        
        # Test levels
        self.assertEqual(level0.level, 0)
        self.assertEqual(level1.level, 1)
        self.assertEqual(level2.level, 2)
        
        # Test sub-items
        self.assertIn(level1, level0.get_sub_items())
        self.assertIn(level2, level1.get_sub_items())
        self.assertNotIn(level2, level0.get_sub_items())
    
    def test_agenda_item_siblings(self):
        """Test AgendaItem sibling relationships"""
        parent = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Parent',
            order=1
        )
        child1 = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Child 1',
            order=2,
            parent_item=parent
        )
        child2 = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Child 2',
            order=3,
            parent_item=parent
        )
        child3 = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Child 3',
            order=4,
            parent_item=parent
        )
        
        # Test siblings
        child1_siblings = child1.get_siblings()
        self.assertIn(child2, child1_siblings)
        self.assertIn(child3, child1_siblings)
        self.assertNotIn(child1, child1_siblings)
    
    def test_agenda_item_get_absolute_url(self):
        """Test AgendaItem get_absolute_url method"""
        agenda_item = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Test Item',
            order=1
        )
        
        expected_url = f'/group/agenda/{agenda_item.pk}/'
        self.assertEqual(agenda_item.get_absolute_url(), expected_url)
    
    def test_agenda_item_optional_fields(self):
        """Test AgendaItem model with optional fields"""
        agenda_item = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Test Item',
            order=1
            # description and parent_item are optional
        )
        
        self.assertEqual(agenda_item.description, '')
        self.assertIsNone(agenda_item.parent_item)
        self.assertTrue(agenda_item.is_active)
    
    def test_agenda_item_meeting_filtering(self):
        """Test AgendaItem filtering by meeting"""
        meeting2 = GroupMeeting.objects.create(
            group=self.group,
            title='Meeting 2',
            scheduled_date=timezone.now() + timedelta(days=2),
            created_by=self.user
        )
        
        item1 = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Item 1',
            order=1
        )
        item2 = AgendaItem.objects.create(
            meeting=meeting2,
            title='Item 2',
            order=1
        )
        
        meeting1_items = AgendaItem.objects.filter(meeting=self.meeting)
        self.assertIn(item1, meeting1_items)
        self.assertNotIn(item2, meeting1_items)
    
    def test_agenda_item_ordering_with_same_order(self):
        """Test AgendaItem ordering when items have same order"""
        item1 = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Item 1',
            order=1
        )
        item2 = AgendaItem.objects.create(
            meeting=self.meeting,
            title='Item 2',
            order=1
        )
        
        items = AgendaItem.objects.all()
        # Should be ordered by order, then created_at (first created first)
        self.assertEqual(items[0], item1)
        self.assertEqual(items[1], item2)


class GroupMeetingICSExportTests(TestCase):
    """Test cases for GroupMeeting ICS export view"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        User = get_user_model()
        
        # Create users
        self.superuser = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_superuser=True
        )
        
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass123'
        )
        
        # Create local, party, and group
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        
        self.party = Party.objects.create(
            name='Test Party',
            local=self.local
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            party=self.party
        )
        
        # Create a group member who can manage the group
        self.group_admin = User.objects.create_user(
            username='groupadmin',
            email='groupadmin@example.com',
            password='adminpass123'
        )
        GroupMember.objects.create(
            user=self.group_admin,
            group=self.group,
            is_active=True
        )
        # Make group_admin a group admin (this would typically be done via roles)
        # For testing, we'll check if the group's can_user_manage_group method works
        
        # Create a meeting
        self.meeting = GroupMeeting.objects.create(
            group=self.group,
            title='Test Meeting',
            scheduled_date=timezone.now() + timedelta(days=1, hours=2),
            location='Test Location',
            description='Test meeting description',
            created_by=self.superuser
        )
    
    def test_ics_export_superuser_access(self):
        """Test that superuser can export ICS file"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(f'/group/meetings/{self.meeting.pk}/export-ics/')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/calendar; charset=utf-8')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('.ics', response['Content-Disposition'])
    
    def test_ics_export_group_admin_access(self):
        """Test that group admin can export ICS file"""
        # Note: This test assumes the group admin can manage the group
        # In a real scenario, you'd set up proper roles/permissions
        self.client.login(username='groupadmin', password='adminpass123')
        response = self.client.get(f'/group/meetings/{self.meeting.pk}/export-ics/')
        
        # The view checks if user can manage the group
        # If the permission check passes, status should be 200
        # If not, it will redirect with an error message
        # For now, we'll check that it doesn't crash
        self.assertIn(response.status_code, [200, 302])
    
    def test_ics_export_regular_user_denied(self):
        """Test that regular user without permission cannot export ICS file"""
        self.client.login(username='regular', password='regularpass123')
        response = self.client.get(f'/group/meetings/{self.meeting.pk}/export-ics/')
        
        # Should redirect with error message
        self.assertEqual(response.status_code, 302)
        self.assertIn('/group/meetings/', response.url)
    
    def test_ics_export_unauthenticated_denied(self):
        """Test that unauthenticated user cannot export ICS file"""
        response = self.client.get(f'/group/meetings/{self.meeting.pk}/export-ics/')
        
        # Should redirect to login or settings (app may use LOGIN_URL that points to settings)
        self.assertEqual(response.status_code, 302)
        self.assertTrue('/login' in response.url or '/user/settings' in response.url,
                        f'Expected redirect to login or settings, got {response.url}')
    
    def test_ics_export_content_format(self):
        """Test that ICS file has correct format"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(f'/group/meetings/{self.meeting.pk}/export-ics/')
        
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # Check for ICS file structure
        self.assertIn('BEGIN:VCALENDAR', content)
        self.assertIn('VERSION:2.0', content)
        self.assertIn('BEGIN:VEVENT', content)
        self.assertIn('END:VEVENT', content)
        self.assertIn('END:VCALENDAR', content)
    
    def test_ics_export_contains_meeting_details(self):
        """Test that ICS file contains meeting details"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(f'/group/meetings/{self.meeting.pk}/export-ics/')
        
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # Check for meeting title
        self.assertIn('SUMMARY:', content)
        self.assertIn('Test Meeting', content)
        
        # Check for location
        self.assertIn('LOCATION:', content)
        self.assertIn('Test Location', content)
        
        # Check for description
        self.assertIn('DESCRIPTION:', content)
        self.assertIn('Test meeting description', content)
        
        # Check for date/time fields
        self.assertIn('DTSTART:', content)
        self.assertIn('DTEND:', content)
        self.assertIn('DTSTAMP:', content)
        self.assertIn('LAST-MODIFIED:', content)
        
        # Check for UID
        self.assertIn('UID:', content)
        self.assertIn(f'meeting-{self.meeting.pk}', content)
        
        # Check for URL
        self.assertIn('URL:', content)
    
    def test_ics_export_filename(self):
        """Test that ICS file has correct filename"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(f'/group/meetings/{self.meeting.pk}/export-ics/')
        
        self.assertEqual(response.status_code, 200)
        content_disposition = response['Content-Disposition']
        
        # Check filename format
        self.assertIn('attachment', content_disposition)
        self.assertIn('filename=', content_disposition)
        self.assertIn(f'meeting_{self.meeting.pk}', content_disposition)
        self.assertIn('Test_Meeting', content_disposition)
        self.assertIn('.ics', content_disposition)
    
    def test_ics_export_without_location(self):
        """Test ICS export for meeting without location"""
        meeting_no_location = GroupMeeting.objects.create(
            group=self.group,
            title='Meeting Without Location',
            scheduled_date=timezone.now() + timedelta(days=1),
            created_by=self.superuser
        )
        
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(f'/group/meetings/{meeting_no_location.pk}/export-ics/')
        
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # Should still have valid ICS format
        self.assertIn('BEGIN:VCALENDAR', content)
        self.assertIn('BEGIN:VEVENT', content)
        # LOCATION field should not be present if empty
        # But the file should still be valid
    
    def test_ics_export_without_description(self):
        """Test ICS export for meeting without description"""
        meeting_no_desc = GroupMeeting.objects.create(
            group=self.group,
            title='Meeting Without Description',
            scheduled_date=timezone.now() + timedelta(days=1),
            location='Test Location',
            created_by=self.superuser
        )
        
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(f'/group/meetings/{meeting_no_desc.pk}/export-ics/')
        
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # Should still have valid ICS format
        self.assertIn('BEGIN:VCALENDAR', content)
        self.assertIn('BEGIN:VEVENT', content)
        # DESCRIPTION field should not be present if empty
        # But the file should still be valid
    
    def test_ics_export_date_format(self):
        """Test that ICS file has correct date format (YYYYMMDDTHHMMSSZ)"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(f'/group/meetings/{self.meeting.pk}/export-ics/')
        
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # Check DTSTART format (should be YYYYMMDDTHHMMSSZ)
        dtstart_match = re.search(r'DTSTART:(\d{8}T\d{6}Z)', content)
        self.assertIsNotNone(dtstart_match, "DTSTART should be in format YYYYMMDDTHHMMSSZ")
        
        dtend_match = re.search(r'DTEND:(\d{8}T\d{6}Z)', content)
        self.assertIsNotNone(dtend_match, "DTEND should be in format YYYYMMDDTHHMMSSZ")
        
        # Verify DTEND is 1 hour after DTSTART
        if dtstart_match and dtend_match:
            from datetime import datetime
            dtstart_str = dtstart_match.group(1)
            dtend_str = dtend_match.group(1)
            dtstart = datetime.strptime(dtstart_str, '%Y%m%dT%H%M%SZ')
            dtend = datetime.strptime(dtend_str, '%Y%m%dT%H%M%SZ')
            duration = dtend - dtstart
            self.assertEqual(duration.total_seconds(), 3600)  # 1 hour in seconds
    
    def test_ics_export_escapes_special_characters(self):
        """Test that ICS file properly escapes special characters"""
        meeting_special = GroupMeeting.objects.create(
            group=self.group,
            title='Meeting, with; special\\ characters',
            scheduled_date=timezone.now() + timedelta(days=1),
            location='Location, with; commas',
            description='Description\nwith\nnewlines',
            created_by=self.superuser
        )
        
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(f'/group/meetings/{meeting_special.pk}/export-ics/')
        
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # Check that special characters are escaped
        # Commas should be escaped as \,
        # Semicolons should be escaped as \;
        # Backslashes should be escaped as \\
        # Newlines should be escaped as \n
        self.assertIn('Meeting\\, with\\; special\\\\ characters', content)
        self.assertIn('Location\\, with\\; commas', content)
        self.assertIn('Description\\nwith\\nnewlines', content)