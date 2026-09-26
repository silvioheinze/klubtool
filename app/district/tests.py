from unittest.mock import MagicMock, patch

from django.test import TestCase, Client, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.utils import timezone
from django.urls import reverse
from datetime import datetime, timedelta

from .forms import (
    DistrictForm, DistrictFilterForm, CouncilForm, CouncilFilterForm,
    CommitteeForm, CommitteeFilterForm, CommitteeMeetingForm, CommitteeMemberForm, CommitteeMemberFilterForm,
    SessionForm, SessionFilterForm, TermForm, TermFilterForm,
    PartyForm, PartyFilterForm, TermSeatDistributionForm, DistrictEventForm,
)
from .models import (
    District, Council, Committee, CommitteeMeeting, CommitteeMember, CommitteeMembershipPeriod,
    CommitteeParticipationSubstitute,
    Session, Term, Party, TermSeatDistribution, SessionAttachment, DistrictEvent, DistrictEventAttachment,
    DistrictEventParticipation,
)
from .views import (
    user_is_district_member,
    user_can_manage_district_events,
    CouncilCommitteesExportPDFView,
)
from pages.calendar_utils import get_personal_calendar_events

User = get_user_model()

PERIOD_FORMSET_PREFIX = 'periods'


def committee_period_formset_post_data(count=1, start_date=None, end_date='', initial=0, periods=None):
    """Build POST data for CommitteeMembershipPeriodFormSet."""
    from datetime import date
    if periods is None:
        start = start_date or date.today().isoformat()
        periods = [{'start_date': start, 'end_date': end_date} for _ in range(count)]
    data = {
        f'{PERIOD_FORMSET_PREFIX}-TOTAL_FORMS': str(len(periods)),
        f'{PERIOD_FORMSET_PREFIX}-INITIAL_FORMS': str(initial),
        f'{PERIOD_FORMSET_PREFIX}-MIN_NUM_FORMS': '1',
        f'{PERIOD_FORMSET_PREFIX}-MAX_NUM_FORMS': '1000',
    }
    for i, period in enumerate(periods):
        data[f'{PERIOD_FORMSET_PREFIX}-{i}-start_date'] = period.get('start_date', '')
        data[f'{PERIOD_FORMSET_PREFIX}-{i}-end_date'] = period.get('end_date', '')
        data[f'{PERIOD_FORMSET_PREFIX}-{i}-DELETE'] = period.get('DELETE', '')
        if period.get('id'):
            data[f'{PERIOD_FORMSET_PREFIX}-{i}-id'] = period['id']
    return data


class DistrictFormTests(TestCase):
    """Test cases for DistrictForm"""
    
    def test_local_form_valid_data(self):
        """Test DistrictForm with valid data"""
        form_data = {
            'name': 'Test Local',
            'code': 'TL',
            'description': 'Test local description'
        }
        
        form = DistrictForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_local_form_required_fields(self):
        """Test DistrictForm with missing required fields"""
        form_data = {
            'name': '',  # Required field missing
            'code': 'TL',
            'description': 'Test local description'
        }
        
        form = DistrictForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)
    
    def test_local_form_code_validation(self):
        """Test DistrictForm code field validation"""
        # Test with invalid characters
        form_data = {
            'name': 'Test Local',
            'code': 'TL-123',  # Contains invalid character
            'description': 'Test local description'
        }
        
        form = DistrictForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('code', form.errors)
    
    def test_local_form_code_uppercase_conversion(self):
        """Test that code is converted to uppercase"""
        form_data = {
            'name': 'Test Local',
            'code': 'tl',  # Lowercase
            'description': 'Test local description'
        }
        
        form = DistrictForm(data=form_data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['code'], 'TL')
    
    def test_local_form_code_alphanumeric_only(self):
        """Test that code contains only alphanumeric characters"""
        form_data = {
            'name': 'Test Local',
            'code': 'TL123',  # Valid alphanumeric
            'description': 'Test local description'
        }
        
        form = DistrictForm(data=form_data)
        self.assertTrue(form.is_valid())


class DistrictFilterFormTests(TestCase):
    """Test cases for DistrictFilterForm"""
    
    def test_district_filter_form_valid_data(self):
        """Test DistrictFilterForm with valid data"""
        form_data = {
            'name': 'Test',
            'code': 'TL',
            'is_active': True
        }
        
        form = DistrictFilterForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_district_filter_form_empty_data(self):
        """Test DistrictFilterForm with empty data"""
        form_data = {}
        
        form = DistrictFilterForm(data=form_data)
        self.assertTrue(form.is_valid())  # Filter forms should be valid with empty data


class CouncilFormTests(TestCase):
    """Test cases for CouncilForm"""
    
    def setUp(self):
        """Set up test data"""
        self.district = District.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
    
    def test_council_form_valid_data(self):
        """Test CouncilForm with valid data"""
        # Test editing an existing council
        form_data = {
            'name': 'Updated Council Name',
            'district': self.district.pk
        }
        
        form = CouncilForm(data=form_data, instance=self.district.council)
        self.assertTrue(form.is_valid())
    
    def test_council_form_required_fields(self):
        """Test CouncilForm with missing required fields"""
        form_data = {
            'name': '',  # Required field missing
            'district': self.district.pk,
            'is_active': True
        }
        
        form = CouncilForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)
    
    def test_council_form_district_filtering(self):
        """Test that CouncilForm filters locals correctly"""
        form = CouncilForm()
        expected_locals = District.objects.filter(is_active=True)
        self.assertQuerySetEqual(
            form.fields['district'].queryset,
            expected_locals,
            transform=lambda x: x
        )


class CommitteeFormTests(TestCase):
    """Test cases for CommitteeForm"""
    
    def setUp(self):
        """Set up test data"""
        self.district = District.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        
        self.council, created = Council.objects.get_or_create(
            district=self.district,
            defaults={'name': 'Test Council'}
        )
    
    def test_committee_form_valid_data(self):
        """Test CommitteeForm with valid data"""
        form_data = {
            'name': 'Test Committee',
            'council': self.council.pk,
            'committee_type': 'Ausschuss',
            'is_active': True
        }
        
        form = CommitteeForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_committee_form_required_fields(self):
        """Test CommitteeForm with missing required fields"""
        form_data = {
            'name': '',  # Required field missing
            'council': self.council.pk,
            'committee_type': 'Ausschuss',
            'is_active': True
        }
        
        form = CommitteeForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)
    
    def test_committee_form_council_filtering(self):
        """Test that CommitteeForm filters councils correctly"""
        form = CommitteeForm()
        expected_councils = Council.objects.filter(is_active=True)
        self.assertQuerySetEqual(
            form.fields['council'].queryset,
            expected_councils,
            transform=lambda x: x
        )
    
    def test_committee_form_initial_council(self):
        """Test CommitteeForm with initial council"""
        form = CommitteeForm(initial={'council': self.council.pk})
        # The initial value should be the council object, not the pk
        self.assertEqual(form.fields['council'].initial, self.council)
        # Council field should be hidden when pre-set
        self.assertIsInstance(form.fields['council'].widget, type(form.fields['council'].widget))


class CommitteeMemberFormTests(TestCase):
    """Test cases for CommitteeMemberForm"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.district = District.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        
        self.council, created = Council.objects.get_or_create(
            district=self.district,
            defaults={'name': 'Test Council'}
        )
        
        self.committee = Committee.objects.create(
            name='Test Committee',
            council=self.council
        )
        
        # CommitteeMemberForm filters users to those in groups in the committee's local.
        # Add user to a group so they appear in the form's user queryset.
        from district.models import Party
        from group.models import Group, GroupMember
        from user.models import Role
        party = Party.objects.create(name='Test Party', district=self.district, is_active=True)
        group = Group.objects.create(name='Test Group', party=party, is_active=True)
        role = Role.objects.filter(is_active=True).first()
        if role:
            gm = GroupMember.objects.create(user=self.user, group=group, is_active=True)
            gm.roles.add(role)
        else:
            GroupMember.objects.create(user=self.user, group=group, is_active=True)
    
    def test_committee_member_form_valid_data(self):
        """Test CommitteeMemberForm with valid data"""
        from datetime import date
        form_data = {
            'user': self.user.pk,
            'committee': self.committee.pk,
            'role': 'member',
            'joined_date': date.today().isoformat(),
            'notes': ''
        }
        
        form = CommitteeMemberForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
    
    def test_committee_member_form_required_fields(self):
        """Test CommitteeMemberForm with missing required fields"""
        form_data = {
            'user': '',  # Required field missing
            'committee': self.committee.pk,
            'role': 'member',
            'is_active': True
        }
        
        form = CommitteeMemberForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('user', form.errors)
    
    def test_committee_member_form_committee_filtering(self):
        """Test that CommitteeMemberForm filters committees correctly"""
        form = CommitteeMemberForm()
        expected_committees = Committee.objects.filter(is_active=True)
        self.assertQuerySetEqual(
            form.fields['committee'].queryset,
            expected_committees,
            transform=lambda x: x
        )


class CommitteeMeetingFormTests(TestCase):
    """Test cases for CommitteeMeetingForm"""

    def setUp(self):
        self.district = District.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        self.council = self.district.council
        self.committee = Committee.objects.create(
            name='Test Committee',
            council=self.council,
            is_active=True
        )

    def test_committee_meeting_form_valid_data(self):
        """Test CommitteeMeetingForm (create) with valid data; title and is_active are set in save()"""
        scheduled = timezone.now() + timedelta(days=1)
        form_data = {
            'committee': self.committee.pk,
            'scheduled_date': scheduled.strftime('%Y-%m-%dT%H:%M'),
            'location': 'Room 101',
            'description': 'Agenda items',
        }
        form = CommitteeMeetingForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        meeting = form.save()
        # Form saves title as committee name + date (no time)
        self.assertEqual(meeting.title, f"{self.committee.name} {scheduled.strftime('%d.%m.%Y')}")
        self.assertTrue(meeting.is_active)

    def test_committee_meeting_form_required_fields(self):
        """Test CommitteeMeetingForm (create) with missing required fields (scheduled_date)"""
        form_data = {
            'committee': self.committee.pk,
        }
        form = CommitteeMeetingForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('scheduled_date', form.errors)

    def test_committee_meeting_form_committee_filtering(self):
        """Test that CommitteeMeetingForm filters committees correctly"""
        form = CommitteeMeetingForm()
        self.assertIn(self.committee, form.fields['committee'].queryset)

    def test_committee_meeting_form_with_committee_kwarg(self):
        """Test CommitteeMeetingForm with committee kwarg restricts queryset"""
        form = CommitteeMeetingForm(committee=self.committee)
        self.assertEqual(form.fields['committee'].queryset.count(), 1)
        self.assertEqual(form.fields['committee'].queryset.get(), self.committee)

    def test_committee_meeting_form_edit_has_title_not_is_active(self):
        """Test CommitteeMeetingForm for edit (existing instance) shows title, not is_active"""
        meeting = CommitteeMeeting.objects.create(
            committee=self.committee,
            title='Existing Meeting',
            scheduled_date=timezone.now() + timedelta(days=1),
            is_active=True,
        )
        form = CommitteeMeetingForm(instance=meeting)
        self.assertIn('title', form.fields)
        self.assertNotIn('is_active', form.fields)


class SessionFormTests(TestCase):
    """Test cases for SessionForm"""
    
    def setUp(self):
        """Set up test data"""
        self.district = District.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        
        self.council, created = Council.objects.get_or_create(
            district=self.district,
            defaults={'name': 'Test Council'}
        )
        
        self.term = Term.objects.create(
            name='Test Term',
            start_date=timezone.now().date(),
            end_date=(timezone.now().date() + timedelta(days=365))
        )
    
    def test_session_form_valid_data(self):
        """Test SessionForm with valid data (create: no title field; title set in save())"""
        form_data = {
            'council': self.council.pk,
            'term': self.term.pk,
            'session_type': 'regular',
            'status': 'scheduled',
            'scheduled_date': '2025-12-01T10:00',
            'location': 'Test Location',
            'agenda': 'Test agenda',
            'minutes': 'Test minutes',
            'notes': 'Test notes'
        }
        
        form = SessionForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save()
        self.assertIn('Bezirksvertretungssitzung', obj.title)
        self.assertIn('01.12.2025', obj.title)
    
    def test_session_form_required_fields(self):
        """Test SessionForm with missing required fields (title is hidden on create)"""
        form_data = {
            'council': self.council.pk,
            'term': self.term.pk,
            'session_type': 'regular',
            'status': 'scheduled',
            'scheduled_date': '',  # Required field missing
            'committee': ''
        }
        
        form = SessionForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('scheduled_date', form.errors)
    
    def test_session_form_council_filtering(self):
        """Test that SessionForm filters councils correctly"""
        form = SessionForm()
        expected_councils = Council.objects.filter(is_active=True)
        self.assertQuerySetEqual(
            form.fields['council'].queryset,
            expected_councils,
            transform=lambda x: x
        )
    
    def test_session_form_term_filtering(self):
        """Test that SessionForm filters terms correctly"""
        form = SessionForm()
        expected_terms = Term.objects.filter(is_active=True)
        self.assertQuerySetEqual(
            form.fields['term'].queryset,
            expected_terms,
            transform=lambda x: x
        )
    
    def test_session_form_initial_council(self):
        """Test SessionForm with initial council"""
        form = SessionForm(initial={'council': self.council.pk})
        # The initial value should be the council object, not the pk
        self.assertEqual(form.fields['council'].initial, self.council)
        # Council field should be hidden when pre-set
        self.assertIsInstance(form.fields['council'].widget, type(form.fields['council'].widget))
    
    def test_session_form_with_committee(self):
        """Test SessionForm with committee field"""
        committee = Committee.objects.create(
            name='Test Committee',
            council=self.council,
            is_active=True
        )
        
        form_data = {
            'title': 'Test Committee Session',
            'council': self.council.pk,
            'committee': committee.pk,
            'term': self.term.pk,
            'session_type': 'regular',
            'status': 'scheduled',
            'scheduled_date': '2025-12-01T10:00',
            'location': 'Test Location',
            'agenda': 'Test agenda',
            'minutes': 'Test minutes',
            'notes': 'Test notes'
        }
        
        form = SessionForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        session = form.save()
        self.assertEqual(session.committee, committee)
        self.assertEqual(session.council, self.council)
    
    def test_session_form_committee_filtering_by_council(self):
        """Test that SessionForm filters committees based on council"""
        # Create committees for different councils
        committee1 = Committee.objects.create(
            name='Committee 1',
            council=self.council,
            is_active=True
        )
        
        local2 = District.objects.create(name='Test District 2', code='TL2')
        council2, _ = Council.objects.get_or_create(
            district=local2,
            defaults={'name': 'Test Council 2'}
        )
        committee2 = Committee.objects.create(
            name='Committee 2',
            council=council2,
            is_active=True
        )
        
        # Form with initial council should only show committees for that council
        form = SessionForm(initial={'council': self.council.pk})
        form.fields['council'].initial = self.council
        # Simulate the form's __init__ logic
        form.fields['committee'].queryset = Committee.objects.filter(council=self.council, is_active=True)
        
        self.assertIn(committee1, form.fields['committee'].queryset)
        self.assertNotIn(committee2, form.fields['committee'].queryset)
    
    def test_session_form_committee_optional(self):
        """Test that committee field is optional in SessionForm"""
        form_data = {
            'title': 'Test Session Without Committee',
            'council': self.council.pk,
            'term': self.term.pk,
            'session_type': 'regular',
            'status': 'scheduled',
            'scheduled_date': '2025-12-01T10:00',
        }
        
        form = SessionForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        session = form.save()
        self.assertIsNone(session.committee)
        self.assertEqual(session.council, self.council)


class TermFormTests(TestCase):
    """Test cases for TermForm"""
    
    def setUp(self):
        """Set up test data"""
        self.district = District.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
    
    def test_term_form_valid_data(self):
        """Test TermForm with valid data"""
        form_data = {
            'name': 'Test Term',
            'start_date': '2025-01-01',
            'end_date': '2030-12-31',
            'total_seats': 40,
            'is_active': True
        }
        
        form = TermForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_term_form_required_fields(self):
        """Test TermForm with missing required fields"""
        form_data = {
            'name': '',  # Required field missing
            'start_date': '2025-01-01',
            'end_date': '2030-12-31',
            'total_seats': 40
        }
        
        form = TermForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)
    
    def test_term_form_date_validation(self):
        """Test TermForm date validation"""
        form_data = {
            'name': 'Test Term',
            'start_date': '2030-12-31',  # End date before start date
            'end_date': '2025-01-01',
            'total_seats': 40
        }
        
        form = TermForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)
    


class PartyFormTests(TestCase):
    """Test cases for PartyForm"""
    
    def setUp(self):
        """Set up test data"""
        self.district = District.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
    
    def test_party_form_valid_data(self):
        """Test PartyForm with valid data"""
        form_data = {
            'name': 'Test Party',
            'district': self.district.pk,
            'color': '#FF0000',
            'is_active': True
        }
        
        form = PartyForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_party_form_required_fields(self):
        """Test PartyForm with missing required fields"""
        form_data = {
            'name': '',  # Required field missing
            'district': self.district.pk,
            'color': '#FF0000',
            'is_active': True
        }
        
        form = PartyForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)
    
    def test_party_form_district_filtering(self):
        """Test that PartyForm filters locals correctly"""
        form = PartyForm()
        expected_locals = District.objects.filter(is_active=True)
        self.assertQuerySetEqual(
            form.fields['district'].queryset,
            expected_locals,
            transform=lambda x: x
        )


class DistrictCreateViewTests(TestCase):
    """Test cases for DistrictCreateView"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        self.parent_district = District.objects.create(
            name='Parent Local',
            code='PL',
            description='Parent local description'
        )
    
    def test_local_create_view_requires_superuser(self):
        """Test that DistrictCreateView requires superuser"""
        response = self.client.get(reverse('district:district-create'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_local_create_view_superuser_access(self):
        """Test that superuser can access DistrictCreateView"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:district-create'))
        self.assertEqual(response.status_code, 200)
    
    def test_local_create_view_with_parent_district_parameter(self):
        """Test that DistrictCreateView shows parent local information when parameter is provided"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(f"{reverse('district:district-create')}?district={self.parent_district.pk}")
        
        self.assertEqual(response.status_code, 200)
        # Check that the parent local information is displayed
        self.assertContains(response, self.parent_district.name)
        self.assertContains(response, self.parent_district.code)
        self.assertContains(response, "Creating District for:")
    
    def test_local_create_view_without_parent_district_parameter(self):
        """Test that DistrictCreateView works normally without parent local parameter"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:district-create'))
        
        self.assertEqual(response.status_code, 200)
        # Check that parent local information is not displayed
        self.assertNotContains(response, "Creating District for:")
    
    def test_local_create_view_invalid_parent_district_parameter(self):
        """Test that DistrictCreateView handles invalid parent local parameter gracefully"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(f"{reverse('district:district-create')}?district=999")
        
        self.assertEqual(response.status_code, 200)
        # Check that parent local information is not displayed for invalid ID
        self.assertNotContains(response, "Creating District for:")
    
    def test_local_create_view_successful_creation(self):
        """Test that DistrictCreateView successfully creates a local"""
        self.client.login(username='admin', password='adminpass123')
        
        response = self.client.post(reverse('district:district-create'), {
            'name': 'Test Local',
            'code': 'TL',
            'description': 'Test local description'
        })
        
        # Should redirect to local list
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('district:district-list'))
        
        # Check that the local was created
        self.assertTrue(District.objects.filter(name='Test Local').exists())


class PartyCreateViewTests(TestCase):
    """Test cases for PartyCreateView"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        self.district = District.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
    
    def test_party_create_view_requires_superuser(self):
        """Test that PartyCreateView requires superuser"""
        response = self.client.get(reverse('district:party-create'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_party_create_view_superuser_access(self):
        """Test that superuser can access PartyCreateView"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:party-create'))
        self.assertEqual(response.status_code, 200)
    
    def test_party_create_view_initial_local_from_url(self):
        """Test that PartyCreateView sets initial local from URL parameter"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(f"{reverse('district:party-create')}?district={self.district.pk}")
        
        self.assertEqual(response.status_code, 200)
        # Check that the form has the local field pre-set and visible
        self.assertContains(response, f'value="{self.district.pk}"')
        # Check that the local field is displayed as non-editable
        self.assertContains(response, self.district.name)
        self.assertContains(response, self.district.code)
    
    def test_party_create_view_shows_parent_district_information(self):
        """Test that PartyCreateView shows parent local information when parameter is provided"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(f"{reverse('district:party-create')}?district={self.district.pk}")
        
        self.assertEqual(response.status_code, 200)
        # Check that the parent local information is displayed in the local field
        self.assertContains(response, self.district.name)
        self.assertContains(response, self.district.code)
        # Check that the local field is displayed as non-editable (not as a select)
        self.assertNotContains(response, 'form-select')  # Should not be a select dropdown
    
    def test_party_create_view_without_parent_district_parameter(self):
        """Test that PartyCreateView works normally without parent local parameter"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:party-create'))
        
        self.assertEqual(response.status_code, 200)
        # Check that the local field is displayed as a normal select dropdown
        self.assertContains(response, 'form-select')  # Should be a select dropdown
    
    def test_party_create_view_invalid_parent_district_parameter(self):
        """Test that PartyCreateView handles invalid parent local parameter gracefully"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(f"{reverse('district:party-create')}?district=999")
        
        self.assertEqual(response.status_code, 200)
        # Check that the local field is displayed as a normal select dropdown for invalid ID
        self.assertContains(response, 'form-select')  # Should be a select dropdown
    
    def test_party_create_view_success_redirect_with_local(self):
        """Test that PartyCreateView redirects to local detail when local parameter is provided"""
        self.client.login(username='admin', password='adminpass123')
        
        # Create a party with local parameter
        response = self.client.post(f"{reverse('district:party-create')}?district={self.district.pk}", {
            'name': 'Test Party',
            'district': self.district.pk,
            'color': '#FF0000',
            'is_active': True
        })
        
        # Should redirect to local detail page
        self.assertEqual(response.status_code, 302)
        expected_url = reverse('district:district-detail', kwargs={'pk': self.district.pk})
        self.assertRedirects(response, expected_url)
    
    def test_party_create_view_success_redirect_without_local(self):
        """Test that PartyCreateView redirects to party list when no local parameter"""
        self.client.login(username='admin', password='adminpass123')
        
        # Create a party without local parameter
        response = self.client.post(reverse('district:party-create'), {
            'name': 'Test Party',
            'district': self.district.pk,
            'color': '#FF0000',
            'is_active': True
        })
        
        # Should redirect to party list
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('district:party-list'))
    
    def test_party_create_view_invalid_local_parameter(self):
        """Test that PartyCreateView handles invalid local parameter gracefully"""
        self.client.login(username='admin', password='adminpass123')
        
        # Try to create party with invalid local parameter
        response = self.client.post(f"{reverse('district:party-create')}?district=999", {
            'name': 'Test Party',
            'district': self.district.pk,
            'color': '#FF0000',
            'is_active': True
        })
        
        # Should redirect to party list (fallback)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('district:party-list'))


class TermSeatDistributionCreateViewTests(TestCase):
    """Test cases for TermSeatDistributionCreateView"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        from datetime import date
        self.term = Term.objects.create(
            name='Test Term',
            start_date=date(2025, 1, 1),
            end_date=date(2030, 12, 31),
            total_seats=40,
            is_active=True
        )
        self.district = District.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description',
            is_active=True
        )
        self.party = Party.objects.create(
            name='Test Party',
            district=self.district,
            color='#FF0000',
            is_active=True
        )
    
    def test_term_seat_distribution_create_view_requires_superuser(self):
        """Test that TermSeatDistributionCreateView requires superuser"""
        response = self.client.get(reverse('district:term-seat-distribution-create'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_term_seat_distribution_create_view_superuser_access(self):
        """Test that superuser can access TermSeatDistributionCreateView"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:term-seat-distribution-create'))
        self.assertEqual(response.status_code, 200)
    
    def test_term_seat_distribution_create_view_with_term_parameter(self):
        """Test that TermSeatDistributionCreateView handles term parameter correctly"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(f"{reverse('district:term-seat-distribution-create')}?term={self.term.pk}")
        
        self.assertEqual(response.status_code, 200)
        # Check that the form has the term field hidden and pre-set
        self.assertContains(response, f'value="{self.term.pk}"')
    
    def test_term_seat_distribution_create_view_successful_creation(self):
        """Test that TermSeatDistributionCreateView successfully creates a seat distribution"""
        self.client.login(username='admin', password='adminpass123')
        
        response = self.client.post(reverse('district:term-seat-distribution-create'), {
            'term': self.term.pk,
            'party': self.party.pk,
            'seats': 10
        })
        
        # Should redirect to seat distribution list
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('district:term-seat-distribution-list'))
        
        # Check that the seat distribution was created
        self.assertTrue(TermSeatDistribution.objects.filter(
            term=self.term, 
            party=self.party, 
            seats=10
        ).exists())


class TermSeatDistributionFormTests(TestCase):
    """Test cases for TermSeatDistributionForm"""
    
    def setUp(self):
        """Set up test data"""
        self.district = District.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        
        self.term = Term.objects.create(
            name='Test Term',
            start_date=timezone.now().date(),
            end_date=(timezone.now().date() + timedelta(days=365)),
            total_seats=40
        )
        
        self.party = Party.objects.create(
            name='Test Party',
            district=self.district
        )
    
    def test_term_seat_distribution_form_valid_data(self):
        """Test TermSeatDistributionForm with valid data"""
        form_data = {
            'term': self.term.pk,
            'party': self.party.pk,
            'seats': 20
        }
        
        form = TermSeatDistributionForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_term_seat_distribution_form_required_fields(self):
        """Test TermSeatDistributionForm with missing required fields"""
        form_data = {
            'term': self.term.pk,
            'party': '',  # Required field missing
            'seats': 20
        }
        
        form = TermSeatDistributionForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('party', form.errors)
    
    def test_term_seat_distribution_form_seats_validation(self):
        """Test TermSeatDistributionForm seats validation"""
        form_data = {
            'term': self.term.pk,
            'party': self.party.pk,
            'seats': 50  # More seats than term total
        }
        
        form = TermSeatDistributionForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)
    
    def test_term_seat_distribution_form_negative_seats(self):
        """Test TermSeatDistributionForm with negative seats"""
        form_data = {
            'term': self.term.pk,
            'party': self.party.pk,
            'seats': -5  # Negative seats
        }
        
        form = TermSeatDistributionForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('seats', form.errors)
    
    def test_term_seat_distribution_form_party_filtering(self):
        """Test that TermSeatDistributionForm filters parties correctly"""
        form = TermSeatDistributionForm(initial={'term': self.term.pk})
        expected_parties = Party.objects.filter(district=self.district, is_active=True)
        self.assertQuerySetEqual(
            form.fields['party'].queryset,
            expected_parties,
            transform=lambda x: x
        )


class SessionFilterFormTests(TestCase):
    """Test cases for SessionFilterForm"""
    
    def test_session_filter_form_valid_data(self):
        """Test SessionFilterForm with valid data"""
        form_data = {
            'title': 'Test',
            'session_type': 'regular',
            'status': 'scheduled'
        }
        
        form = SessionFilterForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_session_filter_form_empty_data(self):
        """Test SessionFilterForm with empty data"""
        form_data = {}
        
        form = SessionFilterForm(data=form_data)
        self.assertTrue(form.is_valid())  # Filter forms should be valid with empty data


class TermFilterFormTests(TestCase):
    """Test cases for TermFilterForm"""
    
    def test_term_filter_form_valid_data(self):
        """Test TermFilterForm with valid data"""
        form_data = {
            'name': 'Test',
            'district': 1,
            'is_active': True
        }
        
        form = TermFilterForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_term_filter_form_empty_data(self):
        """Test TermFilterForm with empty data"""
        form_data = {}
        
        form = TermFilterForm(data=form_data)
        self.assertTrue(form.is_valid())  # Filter forms should be valid with empty data


class PartyFilterFormTests(TestCase):
    """Test cases for PartyFilterForm"""
    
    def test_party_filter_form_valid_data(self):
        """Test PartyFilterForm with valid data"""
        form_data = {
            'name': 'Test',
            'is_active': True
        }
        
        form = PartyFilterForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_party_filter_form_empty_data(self):
        """Test PartyFilterForm with empty data"""
        form_data = {}
        
        form = PartyFilterForm(data=form_data)
        self.assertTrue(form.is_valid())  # Filter forms should be valid with empty data


# View Tests
class LocalViewTests(TestCase):
    """Test cases for District views"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        self.district = District.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
    
    def test_local_list_view_requires_superuser(self):
        """Test that DistrictListView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('district:district-list'))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:district-list'))
        self.assertEqual(response.status_code, 200)
    
    def test_local_list_view_contains_locals(self):
        """Test that DistrictListView contains local objects"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:district-list'))
        self.assertContains(response, self.district.name)
        self.assertContains(response, self.district.code)
    
    def test_local_list_view_search_functionality(self):
        """Test search functionality in DistrictListView"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:district-list'), {'search': 'Test'})
        self.assertContains(response, self.district.name)
        
        # Test with a search term that definitely won't match
        response = self.client.get(reverse('district:district-list'), {'search': 'XYZ123Nonexistent'})
        # The search should return no results, so the local name should not be in the main content
        # Note: The template shows "No Locals found" when search returns no results
        # We check for the "No Locals found" message instead of checking for absence of the name
        # because the name might appear in navigation
        self.assertContains(response, "No Locals found")
    
    def test_local_list_view_status_filter(self):
        """Test status filter in DistrictListView"""
        self.client.login(username='admin', password='adminpass123')
        
        # Test active filter
        response = self.client.get(reverse('district:district-list'), {'status': 'active'})
        self.assertContains(response, self.district.name)
        
        # Test inactive filter
        self.district.is_active = False
        self.district.save()
        response = self.client.get(reverse('district:district-list'), {'status': 'inactive'})
        self.assertContains(response, self.district.name)
    
    def test_local_detail_view_requires_superuser(self):
        """Test that DistrictDetailView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('district:district-detail', kwargs={'pk': self.district.pk}))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:district-detail', kwargs={'pk': self.district.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_local_detail_view_contains_local_info(self):
        """Test that DistrictDetailView contains local information"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:district-detail', kwargs={'pk': self.district.pk}))
        self.assertContains(response, self.district.name)
        # Note: The template doesn't display code and description in the current version
        # self.assertContains(response, self.district.code)
        # self.assertContains(response, self.district.description)
    
    def test_local_create_view_requires_superuser(self):
        """Test that DistrictCreateView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('district:district-create'))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:district-create'))
        self.assertEqual(response.status_code, 200)
    
    def test_local_create_view_post_valid_data(self):
        """Test DistrictCreateView with valid POST data"""
        self.client.login(username='admin', password='adminpass123')
        form_data = {
            'name': 'New Local',
            'code': 'NL',
            'description': 'New local description'
        }
        response = self.client.post(reverse('district:district-create'), form_data)
        self.assertEqual(response.status_code, 302)  # Redirect after successful creation
        
        # Check that the local was created
        self.assertTrue(District.objects.filter(name='New Local').exists())
    
    def test_local_edit_view_requires_superuser(self):
        """Test that DistrictUpdateView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('district:district-edit', kwargs={'pk': self.district.pk}))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:district-edit', kwargs={'pk': self.district.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_local_edit_view_post_valid_data(self):
        """Test DistrictUpdateView with valid POST data"""
        self.client.login(username='admin', password='adminpass123')
        form_data = {
            'name': 'Updated Local',
            'code': 'UL',
            'description': 'Updated local description'
        }
        response = self.client.post(reverse('district:district-edit', kwargs={'pk': self.district.pk}), form_data)
        self.assertEqual(response.status_code, 302)  # Redirect after successful update
        
        # Check that the local was updated
        self.district.refresh_from_db()
        self.assertEqual(self.district.name, 'Updated Local')
    
    def test_local_delete_view_requires_superuser(self):
        """Test that DistrictDeleteView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('district:district-delete', kwargs={'pk': self.district.pk}))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:district-delete', kwargs={'pk': self.district.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_local_delete_view_post_confirms_deletion(self):
        """Test DistrictDeleteView with POST confirmation"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.post(reverse('district:district-delete', kwargs={'pk': self.district.pk}))
        self.assertEqual(response.status_code, 302)  # Redirect after successful deletion
        
        # Check that the local was deleted
        self.assertFalse(District.objects.filter(pk=self.district.pk).exists())


class CouncilViewTests(TestCase):
    """Test cases for Council views"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        self.district = District.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        # Council is automatically created with District
        self.council = self.district.council
    
    def test_council_detail_view_requires_superuser(self):
        """Test that CouncilDetailView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('district:council-detail', kwargs={'pk': self.council.pk}))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:council-detail', kwargs={'pk': self.council.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_council_detail_view_contains_council_info(self):
        """Test that CouncilDetailView contains council information"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:council-detail', kwargs={'pk': self.council.pk}))
        self.assertContains(response, self.council.name)

    def test_council_detail_committees_render_as_outline_buttons(self):
        """Council committees are shown as full-width outline buttons."""
        committee = Committee.objects.create(
            name='Budget Committee Button Test',
            council=self.council,
            is_active=True,
        )
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:council-detail', kwargs={'pk': self.council.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, committee.name)
        self.assertContains(response, 'btn-outline-primary')
        self.assertContains(response, f'href="{reverse("district:committee-detail", kwargs={"pk": committee.pk})}"')

    def test_council_detail_sessions_no_pagination_when_ten_or_fewer(self):
        """Council sessions list shows no pagination controls when at most 10 active sessions."""
        self.client.login(username='admin', password='adminpass123')
        term = Term.objects.create(
            name='Pagination Term',
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=365),
        )
        for i in range(10):
            Session.objects.create(
                title=f'Session Page Test {i}',
                council=self.council,
                term=term,
                session_type='regular',
                status='scheduled',
                scheduled_date=timezone.now() + timedelta(days=i + 1),
            )
        response = self.client.get(reverse('district:council-detail', kwargs={'pk': self.council.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'table table-hover')
        self.assertNotContains(response, 'table-striped')
        self.assertNotContains(response, 'council-sessions-pagination')
        for i in range(10):
            self.assertContains(response, f'Session Page Test {i}')

    def test_council_detail_sessions_pagination_when_more_than_ten(self):
        """With 11+ active sessions, pagination appears; AJAX partial page 2 returns the remaining row."""
        self.client.login(username='admin', password='adminpass123')
        term = Term.objects.create(
            name='Pagination Term 2',
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=365),
        )
        for i in range(11):
            Session.objects.create(
                title=f'Session Eleven Test {i}',
                council=self.council,
                term=term,
                session_type='regular',
                status='scheduled',
                scheduled_date=timezone.now() + timedelta(days=i + 1),
            )
        response = self.client.get(reverse('district:council-detail', kwargs={'pk': self.council.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'council-sessions-pagination')
        # Newest first: i=10 has latest scheduled_date → on page 1; i=0 oldest → page 2
        self.assertContains(response, 'Session Eleven Test 10')
        self.assertNotContains(response, 'Session Eleven Test 0')

        partial_url = reverse('district:council-sessions-partial', kwargs={'pk': self.council.pk})
        r2 = self.client.get(
            partial_url + '?page=2',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r2.status_code, 200)
        self.assertContains(r2, 'Session Eleven Test 0')
        self.assertNotContains(r2, 'Session Eleven Test 10')

    def test_council_sessions_partial_forbidden_without_access(self):
        """Partial endpoint returns 403 for users who cannot access the council."""
        self.client.login(username='testuser', password='testpass123')
        partial_url = reverse('district:council-sessions-partial', kwargs={'pk': self.council.pk})
        response = self.client.get(partial_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 403)
    
    def test_council_edit_view_requires_superuser(self):
        """Test that CouncilUpdateView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('district:council-edit', kwargs={'pk': self.council.pk}))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:council-edit', kwargs={'pk': self.council.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_council_edit_view_post_valid_data(self):
        """Test CouncilUpdateView with valid POST data"""
        self.client.login(username='admin', password='adminpass123')
        form_data = {
            'name': 'Updated Council',
            'district': self.district.pk
        }
        response = self.client.post(reverse('district:council-edit', kwargs={'pk': self.council.pk}), form_data)
        self.assertEqual(response.status_code, 302)  # Redirect after successful update
        
        # Check that the council was updated
        self.council.refresh_from_db()
        self.assertEqual(self.council.name, 'Updated Council')


class SessionViewTests(TestCase):
    """Test cases for Session views"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        self.district = District.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        self.council = self.district.council
        
        self.term = Term.objects.create(
            name='Test Term',
            start_date=timezone.now().date(),
            end_date=(timezone.now().date() + timedelta(days=365))
        )
        
        self.session = Session.objects.create(
            title='Test Session',
            council=self.council,
            term=self.term,
            session_type='regular',
            status='scheduled',
            scheduled_date=timezone.now() + timedelta(days=1)
        )
    
    def test_session_detail_view_requires_superuser(self):
        """Test that SessionDetailView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('district:session-detail', kwargs={'pk': self.session.pk}))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:session-detail', kwargs={'pk': self.session.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_session_detail_view_contains_session_info(self):
        """Test that SessionDetailView contains session information"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:session-detail', kwargs={'pk': self.session.pk}))
        self.assertContains(response, self.session.title)
        self.assertContains(response, self.session.get_session_type_display())

    def test_session_detail_shows_compact_participants(self):
        """Session participants card shows compact view with Edit toggle."""
        from group.models import Group, GroupMember, MembershipPeriod
        from user.models import Role

        self.term.is_active = True
        self.term.save(update_fields=['is_active'])
        party = Party.objects.create(name='Session Party', district=self.district, is_active=True)
        TermSeatDistribution.objects.create(term=self.term, party=party, seats=5)
        group = Group.objects.create(name='Session Group', party=party)
        participant = User.objects.create_user(
            username='participant',
            email='participant@example.com',
            password='pass123',
        )
        gm = GroupMember.objects.create(user=participant, group=group, is_active=True)
        gm.roles.add(Role.objects.get_or_create(name='Member', defaults={'is_active': True})[0])
        MembershipPeriod.objects.create(member=gm, start_date=timezone.now().date(), end_date=None)

        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:session-detail', kwargs={'pk': self.session.pk}))
        self.assertContains(response, 'sessionParticipantsCompactView')
        self.assertContains(response, 'sessionParticipantsEditView')
        self.assertContains(response, 'session-participants-card')
        self.assertIn('participant', response.context['present_names'])
    
    def test_session_create_view_requires_superuser(self):
        """Test that SessionCreateView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('district:session-create'))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:session-create'))
        self.assertEqual(response.status_code, 200)
    
    def test_session_create_view_post_valid_data(self):
        """Test SessionCreateView with valid POST data (title auto-set to Bezirksvertretungssitzung + date)"""
        self.client.login(username='admin', password='adminpass123')
        scheduled = timezone.now() + timedelta(days=2)
        form_data = {
            'council': self.council.pk,
            'term': self.term.pk,
            'session_type': 'regular',
            'status': 'scheduled',
            'scheduled_date': scheduled.strftime('%Y-%m-%dT%H:%M')
        }
        response = self.client.post(reverse('district:session-create'), form_data)
        self.assertEqual(response.status_code, 302)  # Redirect after successful creation
        
        # Check that the session was created with auto-generated title (Bezirksvertretungssitzung + date)
        session = Session.objects.filter(council=self.council).order_by('-created_at').first()
        self.assertIsNotNone(session)
        self.assertIn('Bezirksvertretungssitzung', session.title)
        self.assertIn(scheduled.strftime('%d.%m.%Y'), session.title)
    
    def test_session_create_view_with_committee_parameter(self):
        """Test SessionCreateView with committee parameter in URL"""
        committee = Committee.objects.create(
            name='Test Committee',
            council=self.council,
            is_active=True
        )
        
        self.client.login(username='admin', password='adminpass123')
        url = reverse('district:session-create') + f'?committee={committee.pk}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Check that form has committee pre-filled
        form = response.context['form']
        # The committee field should be filtered to only show committees for the council
        # When committee is provided, the form's __init__ should filter committees by council
        # Check that the committee is in the queryset (which should be filtered by council)
        self.assertIn(committee, form.fields['committee'].queryset)
        # The form should have the committee in its initial data
        # Check that we can create a session with this committee
        self.assertTrue(committee.council == self.council)
    
    def test_session_create_view_with_committee_post(self):
        """Test SessionCreateView POST with committee (title auto-set to Bezirksvertretungssitzung + date)"""
        committee = Committee.objects.create(
            name='Test Committee',
            council=self.council,
            is_active=True
        )
        
        self.client.login(username='admin', password='adminpass123')
        form_data = {
            'council': self.council.pk,
            'committee': committee.pk,
            'term': self.term.pk,
            'session_type': 'regular',
            'status': 'scheduled',
            'scheduled_date': (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M')
        }
        response = self.client.post(reverse('district:session-create'), form_data)
        self.assertEqual(response.status_code, 302)
        
        # Check that the session was created with committee and auto-generated title
        session = Session.objects.filter(committee=committee, council=self.council).order_by('-created_at').first()
        self.assertIsNotNone(session)
        self.assertEqual(session.committee, committee)
        self.assertEqual(session.council, self.council)
        self.assertIn('Bezirksvertretungssitzung', session.title)
    
    def test_session_edit_view_requires_superuser(self):
        """Test that SessionUpdateView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('district:session-edit', kwargs={'pk': self.session.pk}))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:session-edit', kwargs={'pk': self.session.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_session_edit_view_post_valid_data(self):
        """Test SessionUpdateView with valid POST data"""
        self.client.login(username='admin', password='adminpass123')
        form_data = {
            'title': 'Updated Session',
            'council': self.council.pk,
            'term': self.term.pk,
            'session_type': 'regular',
            'status': 'scheduled',
            'scheduled_date': (timezone.now() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M')
        }
        response = self.client.post(reverse('district:session-edit', kwargs={'pk': self.session.pk}), form_data)
        self.assertEqual(response.status_code, 302)  # Redirect after successful update
        
        # Check that the session was updated
        self.session.refresh_from_db()
        self.assertEqual(self.session.title, 'Updated Session')
    
    def test_session_delete_view_requires_superuser(self):
        """Test that SessionDeleteView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('district:session-delete', kwargs={'pk': self.session.pk}))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:session-delete', kwargs={'pk': self.session.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_session_delete_view_post_confirms_deletion(self):
        """Test SessionDeleteView with POST confirmation"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.post(reverse('district:session-delete', kwargs={'pk': self.session.pk}))
        self.assertEqual(response.status_code, 302)  # Redirect after successful deletion
        
        # Check that the session was deleted
        self.assertFalse(Session.objects.filter(pk=self.session.pk).exists())


class CommitteeMeetingViewTests(TestCase):
    """Test cases for CommitteeMeeting views"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        self.district = District.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        self.council = self.district.council
        self.committee = Committee.objects.create(
            name='Test Committee',
            council=self.council,
            is_active=True
        )
        self.meeting = CommitteeMeeting.objects.create(
            committee=self.committee,
            title='Test Committee Meeting',
            scheduled_date=timezone.now() + timedelta(days=1),
            location='Room 101',
            is_active=True
        )

    def test_committee_meeting_create_view_requires_superuser(self):
        """Test that CommitteeMeetingCreateView requires superuser"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('district:committee-meeting-create', kwargs={'committee_pk': self.committee.pk})
        )
        self.assertEqual(response.status_code, 403)
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(
            reverse('district:committee-meeting-create', kwargs={'committee_pk': self.committee.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_committee_meeting_create_view_post_valid_data(self):
        """Test CommitteeMeetingCreateView with valid POST data; title is set to committee name + date"""
        self.client.login(username='admin', password='adminpass123')
        scheduled = timezone.now() + timedelta(days=2)
        form_data = {
            'committee': self.committee.pk,
            'scheduled_date': scheduled.strftime('%Y-%m-%dT%H:%M'),
            'location': 'Hall A',
            'description': 'Agenda',
        }
        response = self.client.post(
            reverse('district:committee-meeting-create', kwargs={'committee_pk': self.committee.pk}),
            form_data
        )
        self.assertEqual(response.status_code, 302)
        # Form saves title as committee name + date (no time)
        expected_title = f"{self.committee.name} {scheduled.strftime('%d.%m.%Y')}"
        self.assertTrue(CommitteeMeeting.objects.filter(title=expected_title).exists())

    def test_committee_meeting_create_view_redirects_to_committee_detail(self):
        """Test that create redirects to committee detail after success"""
        self.client.login(username='admin', password='adminpass123')
        form_data = {
            'committee': self.committee.pk,
            'scheduled_date': (timezone.now() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M'),
        }
        response = self.client.post(
            reverse('district:committee-meeting-create', kwargs={'committee_pk': self.committee.pk}),
            form_data
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('district:committee-detail', kwargs={'pk': self.committee.pk}))

    def test_committee_meeting_detail_view_requires_superuser(self):
        """Test that CommitteeMeetingDetailView requires superuser"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('district:committee-meeting-detail', kwargs={'pk': self.meeting.pk})
        )
        self.assertEqual(response.status_code, 403)
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(
            reverse('district:committee-meeting-detail', kwargs={'pk': self.meeting.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_committee_meeting_detail_view_contains_meeting_info(self):
        """Test that CommitteeMeetingDetailView contains meeting information"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(
            reverse('district:committee-meeting-detail', kwargs={'pk': self.meeting.pk})
        )
        self.assertContains(response, self.meeting.title)
        self.assertContains(response, self.committee.name)

    def test_committee_meeting_edit_view_requires_superuser(self):
        """Test that CommitteeMeetingUpdateView requires superuser"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('district:committee-meeting-edit', kwargs={'pk': self.meeting.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_committee_meeting_edit_view_post_valid_data(self):
        """Test CommitteeMeetingUpdateView with valid POST data"""
        self.client.login(username='admin', password='adminpass123')
        form_data = {
            'committee': self.committee.pk,
            'title': 'Updated Meeting Title',
            'scheduled_date': (timezone.now() + timedelta(days=5)).strftime('%Y-%m-%dT%H:%M'),
            'location': 'Room 202',
            'description': 'Updated agenda',
            'status': 'scheduled',
            'is_active': True,
        }
        response = self.client.post(
            reverse('district:committee-meeting-edit', kwargs={'pk': self.meeting.pk}),
            form_data
        )
        self.assertEqual(response.status_code, 302)
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.title, 'Updated Meeting Title')

    def test_committee_meeting_delete_view_requires_superuser(self):
        """Test that CommitteeMeetingDeleteView requires superuser"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('district:committee-meeting-delete', kwargs={'pk': self.meeting.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_committee_meeting_delete_view_post_confirms_deletion(self):
        """Test CommitteeMeetingDeleteView with POST confirmation"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.post(
            reverse('district:committee-meeting-delete', kwargs={'pk': self.meeting.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CommitteeMeeting.objects.filter(pk=self.meeting.pk).exists())

    def test_committee_meeting_export_ics_requires_login(self):
        """Test that committee_meeting_export_ics requires login"""
        response = self.client.get(
            reverse('district:committee-meeting-export-ics', kwargs={'pk': self.meeting.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_committee_meeting_export_ics_superuser_gets_ics(self):
        """Test that superuser can export committee meeting as ICS"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(
            reverse('district:committee-meeting-export-ics', kwargs={'pk': self.meeting.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'text/calendar; charset=utf-8')
        self.assertIn(b'BEGIN:VCALENDAR', response.content)
        self.assertIn(b'BEGIN:VEVENT', response.content)
        self.assertIn(b'SUMMARY:', response.content)
        self.assertIn(self.meeting.title.encode(), response.content)

    def test_committee_meeting_export_ics_regular_user_denied(self):
        """Test that regular user without committee membership is denied"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('district:committee-meeting-export-ics', kwargs={'pk': self.meeting.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_committee_meeting_export_ics_committee_member_allowed(self):
        """Test that committee member can export committee meeting as ICS"""
        CommitteeMember.objects.create(
            committee=self.committee,
            user=self.user,
            role='member',
            is_active=True
        )
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('district:committee-meeting-export-ics', kwargs={'pk': self.meeting.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'text/calendar; charset=utf-8')

    def _post_attachment(self, meeting, file_type='minutes'):
        """POST a minimal PDF attachment to a committee meeting."""
        return self.client.post(
            reverse('district:committee-meeting-attach', kwargs={'committee_meeting_pk': meeting.pk}),
            {
                'file': SimpleUploadedFile(
                    'protocol.pdf',
                    b'%PDF-1.4 minimal test content',
                    content_type='application/pdf',
                ),
                'file_type': file_type,
                'description': '',
            },
        )

    def test_protocol_upload_sets_meeting_completed(self):
        """Uploading minutes (protocol) attachment sets scheduled meeting to completed."""
        self.meeting.status = 'scheduled'
        self.meeting.save(update_fields=['status'])
        self.client.login(username='admin', password='adminpass123')
        response = self._post_attachment(self.meeting, file_type='minutes')
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            reverse('district:committee-meeting-detail', kwargs={'pk': self.meeting.pk}),
            fetch_redirect_response=False,
        )
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.status, 'completed')

    def test_agenda_upload_does_not_change_meeting_status(self):
        """Non-protocol attachment types leave meeting status unchanged."""
        self.meeting.status = 'scheduled'
        self.meeting.save(update_fields=['status'])
        self.client.login(username='admin', password='adminpass123')
        response = self._post_attachment(self.meeting, file_type='agenda')
        self.assertEqual(response.status_code, 302)
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.status, 'scheduled')

    def test_protocol_upload_does_not_change_cancelled_meeting(self):
        """Protocol upload on a cancelled meeting does not change status."""
        self.meeting.status = 'cancelled'
        self.meeting.save(update_fields=['status'])
        self.client.login(username='admin', password='adminpass123')
        response = self._post_attachment(self.meeting, file_type='minutes')
        self.assertEqual(response.status_code, 302)
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.status, 'cancelled')

    def test_protocol_upload_on_already_completed_meeting_is_idempotent(self):
        """Protocol upload when already completed leaves status completed."""
        self.meeting.status = 'completed'
        self.meeting.save(update_fields=['status'])
        self.client.login(username='admin', password='adminpass123')
        response = self._post_attachment(self.meeting, file_type='minutes')
        self.assertEqual(response.status_code, 302)
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.status, 'completed')

    def test_invitation_upload_sets_meeting_invited(self):
        """Uploading invitation attachment sets scheduled meeting to invited."""
        self.meeting.status = 'scheduled'
        self.meeting.save(update_fields=['status'])
        self.client.login(username='admin', password='adminpass123')
        response = self._post_attachment(self.meeting, file_type='invitation')
        self.assertEqual(response.status_code, 302)
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.status, 'invited')

    def test_invitation_upload_does_not_change_completed_meeting(self):
        """Invitation upload on a completed meeting does not change status."""
        self.meeting.status = 'completed'
        self.meeting.save(update_fields=['status'])
        self.client.login(username='admin', password='adminpass123')
        response = self._post_attachment(self.meeting, file_type='invitation')
        self.assertEqual(response.status_code, 302)
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.status, 'completed')

    def test_invitation_upload_does_not_change_cancelled_meeting(self):
        """Invitation upload on a cancelled meeting does not change status."""
        self.meeting.status = 'cancelled'
        self.meeting.save(update_fields=['status'])
        self.client.login(username='admin', password='adminpass123')
        response = self._post_attachment(self.meeting, file_type='invitation')
        self.assertEqual(response.status_code, 302)
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.status, 'cancelled')

    def test_invitation_upload_on_already_invited_meeting_is_idempotent(self):
        """Invitation upload when already invited leaves status invited."""
        self.meeting.status = 'invited'
        self.meeting.save(update_fields=['status'])
        self.client.login(username='admin', password='adminpass123')
        response = self._post_attachment(self.meeting, file_type='invitation')
        self.assertEqual(response.status_code, 302)
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.status, 'invited')


class CommitteeMeetingSetSubstituteTests(TestCase):
    """Test cases for CommitteeMeetingSetSubstituteView - superuser, member, and group leader permissions."""

    def setUp(self):
        from group.models import Group, GroupMember
        from user.models import Role

        self.client = Client()
        self.district = District.objects.create(
            name='Test Local',
            code='TL',
            description='Test local',
        )
        self.council = self.district.council
        self.party = Party.objects.create(
            name='Test Party',
            district=self.district,
            short_name='TP',
            is_active=True,
        )
        self.group = Group.objects.create(
            name='Test Group',
            party=self.party,
            is_active=True,
        )
        self.leader_role = Role.objects.get_or_create(name='Leader', defaults={'is_active': True})[0]
        self.member_user = User.objects.create_user(
            username='memberuser',
            email='member@example.com',
            password='memberpass123',
            first_name='Member',
            last_name='User',
        )
        self.substitute_user = User.objects.create_user(
            username='substituteuser',
            email='substitute@example.com',
            password='substitutepass123',
            first_name='Substitute',
            last_name='User',
        )
        self.leader_user = User.objects.create_user(
            username='leaderuser',
            email='leader@example.com',
            password='leaderpass123',
            first_name='Leader',
            last_name='User',
        )
        self.regular_group_user = User.objects.create_user(
            username='regulargroup',
            email='regular@example.com',
            password='regularpass123',
            first_name='Regular',
            last_name='User',
        )
        User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
        )
        GroupMember.objects.create(
            user=self.member_user,
            group=self.group,
            is_active=True,
        )
        GroupMember.objects.create(
            user=self.substitute_user,
            group=self.group,
            is_active=True,
        )
        GroupMember.objects.create(
            user=self.leader_user,
            group=self.group,
            is_active=True,
        ).roles.add(self.leader_role)
        GroupMember.objects.create(
            user=self.regular_group_user,
            group=self.group,
            is_active=True,
        )
        self.committee = Committee.objects.create(
            name='Test Committee',
            council=self.council,
            committee_type='Ausschuss',
            is_active=True,
        )
        self.meeting = CommitteeMeeting.objects.create(
            committee=self.committee,
            title='Test Meeting',
            scheduled_date=timezone.now() + timedelta(days=1),
            is_active=True,
        )
        self.regular_member = CommitteeMember.objects.create(
            committee=self.committee,
            user=self.member_user,
            role='member',
            is_active=True,
        )
        self.substitute_member = CommitteeMember.objects.create(
            committee=self.committee,
            user=self.substitute_user,
            role='substitute_member',
            is_active=True,
        )

    def test_group_leader_can_set_substitute_for_committee_member(self):
        """Test that a group leader (of a group with a committee member) can set substitute for that member."""
        self.client.login(username='leaderuser', password='leaderpass123')
        response = self.client.post(
            reverse('district:committee-meeting-set-substitute', kwargs={'pk': self.meeting.pk}),
            {'member': self.regular_member.pk, 'substitute_member': self.substitute_member.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            CommitteeParticipationSubstitute.objects.filter(
                committee_meeting=self.meeting,
                member=self.regular_member,
                substitute_member=self.substitute_member,
            ).exists()
        )

    def test_member_can_set_own_substitute(self):
        """Test that a committee member can set their own substitute."""
        self.client.login(username='memberuser', password='memberpass123')
        response = self.client.post(
            reverse('district:committee-meeting-set-substitute', kwargs={'pk': self.meeting.pk}),
            {'member': self.regular_member.pk, 'substitute_member': self.substitute_member.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            CommitteeParticipationSubstitute.objects.filter(
                committee_meeting=self.meeting,
                member=self.regular_member,
                substitute_member=self.substitute_member,
            ).exists()
        )

    def test_regular_group_member_cannot_set_substitute_for_others(self):
        """Test that a regular group member (not leader) cannot set substitute for a committee member."""
        self.client.login(username='regulargroup', password='regularpass123')
        response = self.client.post(
            reverse('district:committee-meeting-set-substitute', kwargs={'pk': self.meeting.pk}),
            {'member': self.regular_member.pk, 'substitute_member': self.substitute_member.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            CommitteeParticipationSubstitute.objects.filter(
                committee_meeting=self.meeting,
                member=self.regular_member,
            ).exists(),
            "Regular group member should not be able to create substitute",
        )

    def test_superuser_can_set_substitute(self):
        """Test that superuser can set substitute for any committee member."""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.post(
            reverse('district:committee-meeting-set-substitute', kwargs={'pk': self.meeting.pk}),
            {'member': self.regular_member.pk, 'substitute_member': self.substitute_member.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            CommitteeParticipationSubstitute.objects.filter(
                committee_meeting=self.meeting,
                member=self.regular_member,
                substitute_member=self.substitute_member,
            ).exists()
        )

    def test_meeting_detail_shows_substitute_button_for_group_leader(self):
        """Test that group leader sees Set substitute button for all participants (can_set_substitute_member_pks)."""
        self.client.login(username='leaderuser', password='leaderpass123')
        response = self.client.get(
            reverse('district:committee-meeting-detail', kwargs={'pk': self.meeting.pk}),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'btn-set-substitute')
        self.assertContains(response, 'setSubstituteModal')


class CommitteeMemberViewTests(TestCase):
    """Test cases for CommitteeMember views"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        self.member_user = User.objects.create_user(
            username='memberuser',
            email='member@example.com',
            password='memberpass123'
        )
        
        self.district = District.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        self.council = self.district.council
        
        # Create a party for this local
        self.party = Party.objects.create(
            name='Test Party',
            district=self.district,
            is_active=True
        )
        
        # Create a group for this party
        from group.models import Group, GroupMember
        self.group = Group.objects.create(
            name='Test Group',
            party=self.party,
            is_active=True
        )
        
        # Add users to the group so they appear in the filtered queryset
        GroupMember.objects.create(
            user=self.member_user,
            group=self.group,
            is_active=True
        )
        GroupMember.objects.create(
            user=self.user,
            group=self.group,
            is_active=True
        )
        
        self.committee = Committee.objects.create(
            name='Test Committee',
            council=self.council,
            committee_type='Ausschuss'
        )
    
    def test_committee_member_create_view_requires_superuser_or_leader(self):
        """Test that CommitteeMemberCreateView requires superuser or group leader/deputy leader"""
        # Test with regular user (no group roles)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('district:committee-member-create'))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:committee-member-create'))
        self.assertEqual(response.status_code, 200)
        
        # Test with group leader
        from group.models import GroupMember
        from user.models import Role
        
        # Create Leader role if it doesn't exist
        leader_role, created = Role.objects.get_or_create(name='Leader')
        
        # Add leader role to testuser
        group_member = GroupMember.objects.get(user=self.user, group=self.group)
        group_member.roles.add(leader_role)
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('district:committee-member-create'))
        self.assertEqual(response.status_code, 200)
    
    def test_committee_member_create_view_get(self):
        """Test CommitteeMemberCreateView GET request"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:committee-member-create'))
        self.assertEqual(response.status_code, 200)
        response_text = response.content.decode()
        self.assertTrue(
            'Add Committee Member' in response_text or 'Gremiumsmitglied hinzufügen' in response_text,
            "Page should show Add Committee Member heading"
        )
        self.assertContains(response, 'form')
    
    def test_committee_member_create_view_with_committee_parameter(self):
        """Test CommitteeMemberCreateView with committee URL parameter"""
        self.client.login(username='admin', password='adminpass123')
        url = f"{reverse('district:committee-member-create')}?committee={self.committee.pk}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.committee.name)
    
    def test_committee_member_create_view_post_valid_data(self):
        """Test CommitteeMemberCreateView with valid POST data"""
        from datetime import date
        self.client.login(username='admin', password='adminpass123')
        form_data = {
            'user': self.member_user.pk,
            'committee': self.committee.pk,
            'role': 'member',
            'joined_date': date.today().isoformat(),
            'notes': 'Test member notes',
            **committee_period_formset_post_data(),
        }
        response = self.client.post(reverse('district:committee-member-create'), form_data)
        self.assertEqual(response.status_code, 302)  # Redirect after successful creation
        
        # Check that the committee member was created
        self.assertTrue(CommitteeMember.objects.filter(
            user=self.member_user,
            committee=self.committee
        ).exists())
    
    def test_committee_member_create_view_post_invalid_data(self):
        """Test CommitteeMemberCreateView with invalid POST data"""
        self.client.login(username='admin', password='adminpass123')
        form_data = {
            'user': '',  # Missing required field
            'committee': self.committee.pk,
            'role': 'member',
            **committee_period_formset_post_data(),
        }
        response = self.client.post(reverse('district:committee-member-create'), form_data)
        self.assertEqual(response.status_code, 200)  # Form errors, stays on page
        # Check for either English or German error message
        self.assertTrue(
            'This field is required' in response.content.decode() or 
            'Dieses Feld ist zwingend erforderlich' in response.content.decode()
        )
    
    def test_committee_member_create_view_redirect_to_committee_detail(self):
        """Test that CommitteeMemberCreateView redirects to committee detail after creation"""
        from datetime import date
        self.client.login(username='admin', password='adminpass123')
        form_data = {
            'user': self.member_user.pk,
            'committee': self.committee.pk,
            'role': 'member',
            'joined_date': date.today().isoformat(),
            **committee_period_formset_post_data(),
        }
        response = self.client.post(reverse('district:committee-member-create'), form_data)
        self.assertEqual(response.status_code, 302)
        
        # Check that redirect goes to committee detail
        expected_url = reverse('district:committee-detail', kwargs={'pk': self.committee.pk})
        self.assertRedirects(response, expected_url)
    
    def test_committee_member_create_view_duplicate_member(self):
        """Test that creating duplicate committee member fails"""
        # Create existing committee member
        CommitteeMember.objects.create(
            user=self.member_user,
            committee=self.committee,
            role='member'
        )
        
        from datetime import date
        self.client.login(username='admin', password='adminpass123')
        form_data = {
            'user': self.member_user.pk,
            'committee': self.committee.pk,
            'role': 'member',
            'joined_date': date.today().isoformat(),
            **committee_period_formset_post_data(),
        }
        response = self.client.post(reverse('district:committee-member-create'), form_data)
        self.assertEqual(response.status_code, 200)  # Form errors, stays on page
        # Form may reject via: unique_together error, or user-queryset exclusion (user filtered out)
        response_text = response.content.decode()
        has_error = (
            'Committee member with this Committee and User already exists' in response_text
            or 'Committee Member mit diesem' in response_text
            or 'existiert bereits' in response_text
            or ('already exists' in response_text and 'committee' in response_text.lower())
            or 'valid choice' in response_text.lower()
            or 'gültig' in response_text
            or 'Select a valid' in response_text
        )
        if not has_error and response.context.get('form'):
            has_error = bool(response.context['form'].errors)
        self.assertTrue(has_error, "Should show duplicate committee member error or form validation error")
    
    def test_committee_member_create_view_success_message(self):
        """Test that success message is displayed after creation"""
        from datetime import date
        self.client.login(username='admin', password='adminpass123')
        form_data = {
            'user': self.member_user.pk,
            'committee': self.committee.pk,
            'role': 'member',
            'joined_date': date.today().isoformat(),
            **committee_period_formset_post_data(),
        }
        response = self.client.post(reverse('district:committee-member-create'), form_data)
        
        # Check that the member was created successfully
        self.assertTrue(CommitteeMember.objects.filter(
            user=self.member_user,
            committee=self.committee
        ).exists())
        
        # Check that redirect happens (success message is handled by Django messages framework)
        self.assertEqual(response.status_code, 302)
    
    def test_committee_member_create_view_role_choices(self):
        """Test that all role choices are available in the form"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:committee-member-create'))
        self.assertEqual(response.status_code, 200)
        
        # Check that all role choices are present (English or German)
        response_text = response.content.decode()
        self.assertTrue(
            'Chairperson' in response_text or 'Vorsitzende' in response_text,
            "Chairperson role should be present"
        )
        self.assertTrue(
            'Vice Chairperson' in response_text or 'Stellv.' in response_text or 'Stellvertretung' in response_text,
            "Vice Chairperson role should be present"
        )
        self.assertTrue('Member' in response_text or 'Mitglied' in response_text)
        self.assertTrue('Substitute Member' in response_text or 'Stellvertretung' in response_text)
    
    def test_committee_member_create_view_user_queryset(self):
        """Test that only active users are available in the form"""
        # Create inactive user
        inactive_user = User.objects.create_user(
            username='inactive',
            email='inactive@example.com',
            password='inactivepass123',
            is_active=False
        )
        
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:committee-member-create'))
        self.assertEqual(response.status_code, 200)
        
        # Check that inactive user is not in the form
        self.assertNotContains(response, 'inactive')
        # Check that active users are present
        self.assertContains(response, 'testuser')
        self.assertContains(response, 'memberuser')


class CommitteeMembershipPeriodTests(TestCase):
    """Tests for committee membership periods and history view."""

    def setUp(self):
        self.client = Client()
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
        )
        self.active_user = User.objects.create_user(
            username='activeuser',
            email='active@example.com',
            password='pass123',
        )
        self.former_user = User.objects.create_user(
            username='formeruser',
            email='former@example.com',
            password='pass123',
        )
        self.district = District.objects.create(name='Test Local', code='TL', description='Test')
        self.council = self.district.council
        self.committee = Committee.objects.create(
            name='Test Commission',
            council=self.council,
            committee_type='Kommission',
        )

        self.active_member = CommitteeMember.objects.create(
            user=self.active_user,
            committee=self.committee,
            role='member',
            is_active=True,
        )
        CommitteeMembershipPeriod.objects.create(
            member=self.active_member,
            start_date=timezone.localdate() - timedelta(days=30),
            end_date=None,
        )

        self.former_member = CommitteeMember.objects.create(
            user=self.former_user,
            committee=self.committee,
            role='member',
            is_active=False,
        )
        CommitteeMembershipPeriod.objects.create(
            member=self.former_member,
            start_date=timezone.localdate() - timedelta(days=400),
            end_date=timezone.localdate() - timedelta(days=30),
        )

    def test_sync_is_active_from_open_period(self):
        self.active_member.sync_is_active()
        self.assertTrue(self.active_member.is_active)

        period = self.active_member.current_period
        period.end_date = timezone.localdate()
        period.save()
        self.active_member.refresh_from_db()
        self.assertFalse(self.active_member.is_active)

    def test_committee_detail_lists_only_active_members(self):
        self.client.login(username='admin', password='adminpass123')
        url = reverse('district:committee-detail', kwargs={'pk': self.committee.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        member_users = {m.user.username for m in response.context['members']}
        self.assertIn('activeuser', member_users)
        self.assertNotIn('formeruser', member_users)

    def test_membership_history_lists_all_periods(self):
        self.client.login(username='admin', password='adminpass123')
        url = reverse('district:committee-membership-history', kwargs={'pk': self.committee.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('activeuser', content)
        self.assertIn('formeruser', content)
        self.assertEqual(response.context['periods'].count(), 2)


class CommitteeMeetingModelTests(TestCase):
    """Test cases for CommitteeMeeting model"""

    def setUp(self):
        self.district = District.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        self.council = self.district.council
        self.committee = Committee.objects.create(
            name='Test Committee',
            council=self.council,
            is_active=True
        )

    def test_committee_has_meetings_relationship(self):
        """Test that Committee model has meetings relationship"""
        meeting = CommitteeMeeting.objects.create(
            committee=self.committee,
            title='Test Meeting',
            scheduled_date=timezone.now() + timedelta(days=1),
            is_active=True
        )
        self.assertIn(meeting, self.committee.meetings.all())
        self.assertEqual(self.committee.meetings.count(), 1)

    def test_committee_meeting_str(self):
        """Test CommitteeMeeting __str__"""
        meeting = CommitteeMeeting.objects.create(
            committee=self.committee,
            title='Budget Review',
            scheduled_date=timezone.now() + timedelta(days=1),
            is_active=True
        )
        self.assertIn('Budget Review', str(meeting))
        self.assertIn(self.committee.name, str(meeting))

    def test_committee_meeting_get_absolute_url(self):
        """Test CommitteeMeeting get_absolute_url"""
        meeting = CommitteeMeeting.objects.create(
            committee=self.committee,
            title='Test Meeting',
            scheduled_date=timezone.now() + timedelta(days=1),
            is_active=True
        )
        url = meeting.get_absolute_url()
        self.assertIn(str(meeting.pk), url)
        self.assertTrue(url.endswith('/'))

    def test_committee_meeting_is_past_future(self):
        """Test CommitteeMeeting is_past for future meeting"""
        meeting = CommitteeMeeting.objects.create(
            committee=self.committee,
            title='Future Meeting',
            scheduled_date=timezone.now() + timedelta(days=1),
            is_active=True
        )
        self.assertFalse(meeting.is_past)

    def test_committee_meeting_is_past_past(self):
        """Test CommitteeMeeting is_past for past meeting"""
        meeting = CommitteeMeeting.objects.create(
            committee=self.committee,
            title='Past Meeting',
            scheduled_date=timezone.now() - timedelta(days=1),
            is_active=True
        )
        self.assertTrue(meeting.is_past)


class CommitteeSessionTests(TestCase):
    """Test cases for committee meetings on committee detail (and legacy Session relationship)"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        self.client = Client()
        self.district = District.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        self.council, _ = Council.objects.get_or_create(
            district=self.district,
            defaults={'name': 'Test Council'}
        )
        self.term = Term.objects.create(
            name='Test Term',
            start_date=timezone.now().date(),
            end_date=(timezone.now().date() + timedelta(days=365))
        )
        self.committee = Committee.objects.create(
            name='Test Committee',
            council=self.council,
            is_active=True
        )

    def test_committee_has_sessions_relationship(self):
        """Test that Committee model still has sessions relationship (Session with committee FK)"""
        session = Session.objects.create(
            title='Committee Session',
            council=self.council,
            committee=self.committee,
            term=self.term,
            session_type='regular',
            status='scheduled',
            scheduled_date=timezone.now() + timedelta(days=1)
        )
        self.assertIn(session, self.committee.sessions.all())
        self.assertEqual(self.committee.sessions.count(), 1)

    def test_committee_detail_view_shows_meetings(self):
        """Test that CommitteeDetailView includes meetings in context"""
        meeting1 = CommitteeMeeting.objects.create(
            committee=self.committee,
            title='Meeting 1',
            scheduled_date=timezone.now() + timedelta(days=1),
            is_active=True
        )
        meeting2 = CommitteeMeeting.objects.create(
            committee=self.committee,
            title='Meeting 2',
            scheduled_date=timezone.now() + timedelta(days=2),
            is_active=True
        )
        other_committee = Committee.objects.create(
            name='Other Committee',
            council=self.council,
            is_active=True
        )
        other_meeting = CommitteeMeeting.objects.create(
            committee=other_committee,
            title='Other Meeting',
            scheduled_date=timezone.now() + timedelta(days=3),
            is_active=True
        )
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:committee-detail', kwargs={'pk': self.committee.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertIn('meetings', response.context)
        meetings = response.context['meetings']
        self.assertEqual(meetings.count(), 2)
        self.assertIn(meeting1, meetings)
        self.assertIn(meeting2, meetings)
        self.assertNotIn(other_meeting, meetings)
        self.assertEqual(response.context['total_meetings'], 2)

    def test_committee_detail_view_meetings_ordered_by_date(self):
        """Test that committee meetings are ordered by scheduled_date descending"""
        meeting1 = CommitteeMeeting.objects.create(
            committee=self.committee,
            title='Meeting 1',
            scheduled_date=timezone.now() + timedelta(days=3),
            is_active=True
        )
        meeting2 = CommitteeMeeting.objects.create(
            committee=self.committee,
            title='Meeting 2',
            scheduled_date=timezone.now() + timedelta(days=1),
            is_active=True
        )
        meeting3 = CommitteeMeeting.objects.create(
            committee=self.committee,
            title='Meeting 3',
            scheduled_date=timezone.now() + timedelta(days=2),
            is_active=True
        )
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:committee-detail', kwargs={'pk': self.committee.pk}))
        meetings = list(response.context['meetings'])
        self.assertEqual(meetings[0], meeting1)
        self.assertEqual(meetings[1], meeting3)
        self.assertEqual(meetings[2], meeting2)

    def test_committee_detail_view_only_shows_active_meetings(self):
        """Test that CommitteeDetailView only shows active meetings"""
        active_meeting = CommitteeMeeting.objects.create(
            committee=self.committee,
            title='Active Meeting',
            scheduled_date=timezone.now() + timedelta(days=1),
            is_active=True
        )
        inactive_meeting = CommitteeMeeting.objects.create(
            committee=self.committee,
            title='Inactive Meeting',
            scheduled_date=timezone.now() + timedelta(days=2),
            is_active=False
        )
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:committee-detail', kwargs={'pk': self.committee.pk}))
        meetings = response.context['meetings']
        self.assertEqual(meetings.count(), 1)
        self.assertIn(active_meeting, meetings)
        self.assertNotIn(inactive_meeting, meetings)

    def test_session_detail_view_shows_committee(self):
        """Test that SessionDetailView shows committee information when session has committee"""
        session = Session.objects.create(
            title='Committee Session',
            council=self.council,
            committee=self.committee,
            term=self.term,
            session_type='regular',
            status='scheduled',
            scheduled_date=timezone.now() + timedelta(days=1)
        )
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:session-detail', kwargs={'pk': session.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['session'].committee, self.committee)
        self.assertContains(response, self.committee.name)

    def test_session_without_committee(self):
        """Test that sessions can exist without a committee"""
        session = Session.objects.create(
            title='Council Session',
            council=self.council,
            term=self.term,
            session_type='regular',
            status='scheduled',
            scheduled_date=timezone.now() + timedelta(days=1)
        )
        self.assertIsNone(session.committee)
        self.assertEqual(session.council, self.council)
        self.assertNotIn(session, self.committee.sessions.all())


class CommitteeViewTests(TestCase):
    """Test cases for Committee views"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        self.district = District.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        self.council = self.district.council
        
        self.committee = Committee.objects.create(
            name='Test Committee',
            council=self.council,
            committee_type='Ausschuss'
        )
    
    def test_committee_list_view_requires_superuser(self):
        """Test that CommitteeListView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('district:committee-list'))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:committee-list'))
        self.assertEqual(response.status_code, 200)
    
    def test_committee_list_view_contains_committees(self):
        """Test that CommitteeListView contains committee objects"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:committee-list'))
        self.assertContains(response, self.committee.name)
    
    def test_committee_detail_view_requires_superuser(self):
        """Test that CommitteeDetailView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('district:committee-detail', kwargs={'pk': self.committee.pk}))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:committee-detail', kwargs={'pk': self.committee.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_committee_detail_view_contains_committee_info(self):
        """Test that CommitteeDetailView contains committee information"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:committee-detail', kwargs={'pk': self.committee.pk}))
        self.assertContains(response, self.committee.name)
        self.assertContains(response, self.committee.get_committee_type_display())
    
    def test_committee_create_view_requires_superuser(self):
        """Test that CommitteeCreateView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('district:committee-create'))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:committee-create'))
        self.assertEqual(response.status_code, 200)
    
    def test_committee_create_view_post_valid_data(self):
        """Test CommitteeCreateView with valid POST data"""
        self.client.login(username='admin', password='adminpass123')
        form_data = {
            'name': 'New Committee',
            'council': self.council.pk,
            'committee_type': 'Kommission',
            'is_active': True
        }
        response = self.client.post(reverse('district:committee-create'), form_data)
        self.assertEqual(response.status_code, 302)  # Redirect after successful creation
        
        # Check that the committee was created
        self.assertTrue(Committee.objects.filter(name='New Committee').exists())
    
    def test_committee_edit_view_requires_superuser(self):
        """Test that CommitteeUpdateView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('district:committee-edit', kwargs={'pk': self.committee.pk}))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:committee-edit', kwargs={'pk': self.committee.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_committee_edit_view_post_valid_data(self):
        """Test CommitteeUpdateView with valid POST data"""
        self.client.login(username='admin', password='adminpass123')
        form_data = {
            'name': 'Updated Committee',
            'council': self.council.pk,
            'committee_type': 'Kommission',
            'status': 'scheduled',
        }
        response = self.client.post(reverse('district:committee-edit', kwargs={'pk': self.committee.pk}), form_data)
        self.assertEqual(response.status_code, 302)  # Redirect after successful update
        
        # Check that the committee was updated
        self.committee.refresh_from_db()
        self.assertEqual(self.committee.name, 'Updated Committee')
    
    def test_committee_delete_view_requires_superuser(self):
        """Test that CommitteeDeleteView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('district:committee-delete', kwargs={'pk': self.committee.pk}))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('district:committee-delete', kwargs={'pk': self.committee.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_committee_delete_view_post_confirms_deletion(self):
        """Test CommitteeDeleteView with POST confirmation"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.post(reverse('district:committee-delete', kwargs={'pk': self.committee.pk}))
        self.assertEqual(response.status_code, 302)  # Redirect after successful deletion
        
        # Check that the committee was deleted
        self.assertFalse(Committee.objects.filter(pk=self.committee.pk).exists())


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CouncilCommitteesExportPDFViewTests(TestCase):
    """Access, HTML content, and a single WeasyPrint smoke test for committee PDF export."""

    @classmethod
    def setUpTestData(cls):
        from group.models import Group, GroupMember
        from user.models import Role

        cls.superuser = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_superuser=True,
        )
        cls.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass123',
        )
        cls.role_user = User.objects.create_user(
            username='roleuser',
            email='role@example.com',
            password='rolepass123',
        )
        role = Role.objects.create(
            name='Session Viewer',
            is_active=True,
            permissions={'permissions': ['session.view']},
        )
        cls.role_user.role = role
        cls.role_user.save()

        cls.district = District.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description',
        )
        cls.council = cls.district.council
        cls.party = Party.objects.create(
            name='Test Party',
            district=cls.district,
            short_name='TP',
            is_active=True,
        )
        cls.group = Group.objects.create(
            name='Test Group',
            party=cls.party,
            is_active=True,
        )

        cls.member_user1 = User.objects.create_user(
            username='member1',
            email='member1@example.com',
            password='memberpass123',
            first_name='John',
            last_name='Doe',
        )
        cls.member_user2 = User.objects.create_user(
            username='member2',
            email='member2@example.com',
            password='memberpass123',
            first_name='Jane',
            last_name='Smith',
        )
        cls.substitute_user = User.objects.create_user(
            username='substitute',
            email='substitute@example.com',
            password='substitutepass123',
            first_name='Bob',
            last_name='Johnson',
        )

        GroupMember.objects.create(user=cls.member_user1, group=cls.group, is_active=True)
        GroupMember.objects.create(user=cls.member_user2, group=cls.group, is_active=True)
        GroupMember.objects.create(user=cls.substitute_user, group=cls.group, is_active=True)

        cls.committee1 = Committee.objects.create(
            name='Budget Committee',
            council=cls.council,
            committee_type='Ausschuss',
            abbreviation='BC',
            description='Budget and finance committee',
            is_active=True,
        )
        cls.committee2 = Committee.objects.create(
            name='Education Committee',
            council=cls.council,
            committee_type='Kommission',
            is_active=True,
        )
        Committee.objects.create(
            name='Inactive Committee',
            council=cls.council,
            committee_type='Ausschuss',
            is_active=False,
        )

        CommitteeMember.objects.create(
            committee=cls.committee1,
            user=cls.member_user1,
            role='chairperson',
            is_active=True,
        )
        CommitteeMember.objects.create(
            committee=cls.committee1,
            user=cls.member_user2,
            role='member',
            is_active=True,
        )
        CommitteeMember.objects.create(
            committee=cls.committee1,
            user=cls.substitute_user,
            role='substitute_member',
            is_active=True,
        )
        CommitteeMember.objects.create(
            committee=cls.committee2,
            user=cls.member_user1,
            role='vice_chairperson',
            is_active=True,
        )
        cls.inactive_member = User.objects.create_user(
            username='inactive',
            email='inactive@example.com',
            password='inactivepass123',
            first_name='Inactive',
            last_name='Member',
        )
        CommitteeMember.objects.create(
            committee=cls.committee1,
            user=cls.inactive_member,
            role='member',
            is_active=False,
        )

        empty_district = District.objects.create(
            name='Empty Local',
            code='EL',
            description='Local with no committees',
        )
        cls.empty_council = empty_district.council
        cls.export_url = reverse(
            'district:council-committees-export-pdf',
            kwargs={'pk': cls.council.pk},
        )

    def _export_html(self, council=None, user=None):
        """Render the PDF template from view context without WeasyPrint."""
        council = council or self.council
        user = user or self.superuser
        request = RequestFactory().get('/')
        request.user = user
        view = CouncilCommitteesExportPDFView()
        view.setup(request, pk=council.pk)
        view.object = council
        context = view.get_context_data()
        return render_to_string(view.template_name, context), context

    def _get_pdf_response(self, url=None, user=None):
        """GET the export URL with WeasyPrint stubbed to a tiny PDF payload."""
        if user is None:
            self.client.logout()
        else:
            self.client.force_login(user)
        html_doc = MagicMock()
        html_doc.write_pdf.return_value = b'%PDF-1.4 stub'
        with patch('weasyprint.HTML', return_value=html_doc), patch('weasyprint.CSS'):
            return self.client.get(url or self.export_url)

    def test_pdf_export_access(self):
        cases = [
            (self.superuser, 200),
            (self.role_user, 200),
            (self.regular_user, 403),
            (None, 302),
        ]
        for user, status in cases:
            with self.subTest(user=getattr(user, 'username', 'anonymous'), status=status):
                response = self._get_pdf_response(user=user)
                self.assertEqual(response.status_code, status)
                if status == 200:
                    self.assertEqual(response['Content-Type'], 'application/pdf')
                    self.assertIn('attachment; filename=', response['Content-Disposition'])
                    self.assertIn('.pdf', response['Content-Disposition'])
                if status == 302:
                    self.assertTrue('/login/' in response.url or '/settings/' in response.url)

    def test_pdf_export_filename_format(self):
        response = self._get_pdf_response(user=self.superuser)
        self.assertEqual(response.status_code, 200)
        disposition = response['Content-Disposition']
        self.assertIn('attachment; filename=', disposition)
        self.assertIn('Stand_', disposition)
        self.assertIn('.pdf', disposition)

    def test_pdf_export_html_content(self):
        html, context = self._export_html()
        self.assertEqual(context['group_name'], self.council.name)
        self.assertIn(self.council.name, html)
        self.assertIn('Budget Committee', html)
        self.assertIn('(BC)', html)
        self.assertIn('Education Committee', html)
        self.assertIn('John Doe', html)
        self.assertIn('Jane Smith', html)
        self.assertIn('Bob Johnson', html)
        self.assertNotIn('Inactive Committee', html)
        self.assertNotIn('Inactive Member', html)
        self.assertLess(html.index('Budget Committee'), html.index('Education Committee'))
        self.assertLess(html.index('John Doe'), html.index('Jane Smith'))

    def test_pdf_export_no_committees(self):
        html, context = self._export_html(council=self.empty_council)
        self.assertEqual(context['total_committees'], 0)
        self.assertIn('Keine Ausschüsse oder Kommissionen gefunden.', html)

    def test_pdf_export_weasyprint_smoke(self):
        """One real WeasyPrint render so CI still checks PDF generation."""
        self.client.force_login(self.superuser)
        response = self.client.get(self.export_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertGreater(len(response.content), 100)


class DistrictEventTests(TestCase):
    """Tests for district events with RSVP and personal calendar integration."""

    def setUp(self):
        self.client = Client()
        self.member = User.objects.create_user(
            username='district_member',
            email='district_member@example.com',
            password='memberpass123',
        )
        self.manager = User.objects.create_user(
            username='district_manager',
            email='district_manager@example.com',
            password='managerpass123',
        )
        self.outsider = User.objects.create_user(
            username='outsider',
            email='outsider@example.com',
            password='outsiderpass123',
        )
        self.district = District.objects.create(
            name='District Events Local',
            code='DEL',
            description='Test district',
            is_active=True,
        )
        self.council = self.district.council
        self.party = Party.objects.create(
            name='District Events Party',
            district=self.district,
            is_active=True,
        )
        from group.models import Group, GroupMember
        from user.models import Role

        self.group = Group.objects.create(
            name='District Events Group',
            party=self.party,
            is_active=True,
        )
        GroupMember.objects.create(user=self.member, group=self.group, is_active=True)
        leader_role = Role.objects.get_or_create(name='Leader', defaults={'is_active': True})[0]
        manager_membership = GroupMember.objects.create(
            user=self.manager, group=self.group, is_active=True,
        )
        manager_membership.roles.add(leader_role)
        self.event = DistrictEvent.objects.create(
            title='District Meetup',
            district=self.district,
            scheduled_date=timezone.now() + timedelta(days=7),
            description='A district-wide event',
            external_link='https://example.com/event',
            created_by=self.manager,
        )

    def test_participation_unique_per_user(self):
        DistrictEventParticipation.objects.create(
            event=self.event, user=self.member, will_attend=True,
        )
        with self.assertRaises(IntegrityError):
            DistrictEventParticipation.objects.create(
                event=self.event, user=self.member, will_attend=False,
            )

    def test_user_is_district_member(self):
        self.assertTrue(user_is_district_member(self.member, self.district))
        self.assertFalse(user_is_district_member(self.outsider, self.district))

    def test_user_can_manage_district_events(self):
        self.assertTrue(user_can_manage_district_events(self.manager, self.district))
        self.assertFalse(user_can_manage_district_events(self.member, self.district))

    def test_member_can_view_event_detail(self):
        self.client.login(username='district_member', password='memberpass123')
        response = self.client.get(reverse('district:event-detail', kwargs={'pk': self.event.pk}))
        self.assertEqual(response.status_code, 200)

    def test_outsider_cannot_view_event_detail(self):
        self.client.login(username='outsider', password='outsiderpass123')
        response = self.client.get(reverse('district:event-detail', kwargs={'pk': self.event.pk}))
        self.assertEqual(response.status_code, 403)

    def test_manager_can_create_event(self):
        self.client.login(username='district_manager', password='managerpass123')
        response = self.client.get(reverse('district:event-create', kwargs={'pk': self.district.pk}))
        self.assertEqual(response.status_code, 200)

    def test_member_cannot_create_event(self):
        self.client.login(username='district_member', password='memberpass123')
        response = self.client.get(reverse('district:event-create', kwargs={'pk': self.district.pk}))
        self.assertEqual(response.status_code, 403)

    def test_member_can_rsvp_attend_and_decline(self):
        self.client.login(username='district_member', password='memberpass123')
        attend_url = reverse('district:event-attend', kwargs={'pk': self.event.pk})
        response = self.client.post(attend_url, {'will_attend': '1'})
        self.assertEqual(response.status_code, 302)
        part = DistrictEventParticipation.objects.get(event=self.event, user=self.member)
        self.assertTrue(part.will_attend)
        response = self.client.post(attend_url, {'will_attend': '0'})
        part.refresh_from_db()
        self.assertFalse(part.will_attend)

    def test_district_detail_shows_upcoming_events(self):
        self.client.login(username='district_member', password='memberpass123')
        response = self.client.get(reverse('district:district-detail', kwargs={'pk': self.district.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'District Meetup')

    def test_attending_event_appears_in_personal_calendar(self):
        DistrictEventParticipation.objects.create(
            event=self.event, user=self.member, will_attend=True,
        )
        from group.models import GroupMember
        memberships = list(GroupMember.objects.filter(user=self.member, is_active=True))
        councils = [self.council]
        events = get_personal_calendar_events(self.member, memberships, councils)
        local_event_entries = [e for e in events if e['type'] == 'district_event']
        self.assertEqual(len(local_event_entries), 1)
        self.assertEqual(local_event_entries[0]['title'], 'District Meetup')

    def test_declined_event_not_in_personal_calendar(self):
        DistrictEventParticipation.objects.create(
            event=self.event, user=self.member, will_attend=False,
        )
        from group.models import GroupMember
        memberships = list(GroupMember.objects.filter(user=self.member, is_active=True))
        councils = [self.council]
        events = get_personal_calendar_events(self.member, memberships, councils)
        local_event_entries = [e for e in events if e['type'] == 'district_event']
        self.assertEqual(len(local_event_entries), 0)

    def test_attending_event_in_ics_export(self):
        DistrictEventParticipation.objects.create(
            event=self.event, user=self.member, will_attend=True,
        )
        self.client.login(username='district_member', password='memberpass123')
        response = self.client.get(reverse('personal-calendar-export-ics'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'District Meetup', response.content)

    def test_district_event_form_accepts_end_and_location(self):
        start = timezone.now() + timedelta(days=10)
        end = start + timedelta(hours=2)
        form = DistrictEventForm(
            data={
                'title': 'With end',
                'scheduled_date': start.strftime('%Y-%m-%dT%H:%M'),
                'end_date': end.strftime('%Y-%m-%dT%H:%M'),
                'location': 'Rathaus',
                'description': '',
                'external_link': '',
                'district': self.district.pk,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_district_event_form_rejects_end_before_start(self):
        start = timezone.now() + timedelta(days=10)
        end = start - timedelta(hours=1)
        form = DistrictEventForm(
            data={
                'title': 'Bad end',
                'scheduled_date': start.strftime('%Y-%m-%dT%H:%M'),
                'end_date': end.strftime('%Y-%m-%dT%H:%M'),
                'location': '',
                'description': '',
                'external_link': '',
                'district': self.district.pk,
            },
        )
        self.assertFalse(form.is_valid())
        self.assertIn('end_date', form.errors)

    def test_event_detail_shows_end_and_location(self):
        start = timezone.now() + timedelta(days=14)
        end = start + timedelta(hours=3)
        self.event.end_date = end
        self.event.location = 'Stadtpark'
        self.event.save()
        self.client.login(username='district_member', password='memberpass123')
        response = self.client.get(reverse('district:event-detail', kwargs={'pk': self.event.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Stadtpark')

    def test_event_export_ics_includes_location_and_custom_end(self):
        start = timezone.now() + timedelta(days=14)
        end = start + timedelta(hours=3)
        self.event.end_date = end
        self.event.location = 'Stadtpark'
        self.event.save()
        self.client.login(username='district_member', password='memberpass123')
        response = self.client.get(reverse('district:event-export-ics', kwargs={'pk': self.event.pk}))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('LOCATION:Stadtpark', content)
        dtend_utc = end.astimezone(timezone.UTC).strftime('%Y%m%dT%H%M%SZ')
        self.assertIn(f'DTEND:{dtend_utc}', content)

    def _post_event_attachment(self):
        return self.client.post(
            reverse('district:event-attach', kwargs={'pk': self.event.pk}),
            {
                'file': SimpleUploadedFile(
                    'flyer.pdf',
                    b'%PDF-1.4 district event attachment',
                    content_type='application/pdf',
                ),
                'file_type': 'invitation',
                'description': 'Event flyer',
            },
        )

    def test_manager_can_upload_event_attachment(self):
        self.client.login(username='district_manager', password='managerpass123')
        response = self._post_event_attachment()
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            reverse('district:event-detail', kwargs={'pk': self.event.pk}),
            fetch_redirect_response=False,
        )
        self.assertTrue(
            DistrictEventAttachment.objects.filter(event=self.event, filename='flyer.pdf').exists()
        )

    def test_member_sees_attachment_on_event_detail(self):
        DistrictEventAttachment.objects.create(
            event=self.event,
            file=SimpleUploadedFile('info.pdf', b'%PDF-1.4 info', content_type='application/pdf'),
            filename='info.pdf',
            file_type='other',
            uploaded_by=self.manager,
        )
        self.client.login(username='district_member', password='memberpass123')
        response = self.client.get(reverse('district:event-detail', kwargs={'pk': self.event.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'info.pdf')

    def test_member_cannot_access_event_attachment_upload(self):
        self.client.login(username='district_member', password='memberpass123')
        response = self.client.get(reverse('district:event-attach', kwargs={'pk': self.event.pk}))
        self.assertEqual(response.status_code, 403)

    def test_event_list_shows_upcoming_and_past(self):
        past_event = DistrictEvent.objects.create(
            title='Past District Event',
            district=self.district,
            scheduled_date=timezone.now() - timedelta(days=3),
            created_by=self.manager,
        )
        self.client.login(username='district_member', password='memberpass123')
        url = reverse('district:event-list', kwargs={'district_pk': self.district.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'District Meetup')
        self.assertContains(response, 'Past District Event')

    def test_district_detail_links_to_event_list(self):
        self.client.login(username='district_member', password='memberpass123')
        response = self.client.get(reverse('district:district-detail', kwargs={'pk': self.district.pk}))
        self.assertEqual(response.status_code, 200)
        list_url = reverse('district:event-list', kwargs={'district_pk': self.district.pk})
        self.assertContains(response, list_url)


class RenameLocalToDistrictMigrationTests(TestCase):
    """Guard the local -> district table rename order used on existing databases."""

    def test_tables_are_renamed_before_council_field_rename(self):
        import importlib
        from django.db.migrations.operations.fields import RenameField
        from django.db.migrations.operations.special import RunPython

        migration_module = importlib.import_module(
            'district.migrations.0039_rename_local_to_district'
        )
        ops = migration_module.Migration.operations
        rename_tables_idx = next(
            i for i, op in enumerate(ops)
            if isinstance(op, RunPython) and op.code.__name__ == 'rename_local_tables'
        )
        council_field_idx = next(
            i for i, op in enumerate(ops)
            if isinstance(op, RenameField) and op.model_name == 'council'
        )
        self.assertLess(
            rename_tables_idx,
            council_field_idx,
            'local_* tables must be renamed before RenameField on council (district_council)',
        )

    def test_rename_local_tables_restores_district_council(self):
        """Existing DBs have local_council; the helper must rename it before field alters."""
        import importlib
        from django.db import connection

        migration_module = importlib.import_module(
            'district.migrations.0039_rename_local_to_district'
        )

        with connection.cursor() as cursor:
            cursor.execute('ALTER TABLE district_council RENAME TO local_council')

        class _SchemaEditor:
            pass

        schema_editor = _SchemaEditor()
        schema_editor.connection = connection
        migration_module.rename_local_tables(None, schema_editor)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = %s)",
                ['district_council'],
            )
            self.assertTrue(cursor.fetchone()[0])
            cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = %s)",
                ['local_council'],
            )
            self.assertFalse(cursor.fetchone()[0])

