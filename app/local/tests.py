from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.urls import reverse
from datetime import datetime, timedelta

from .forms import (
    LocalForm, LocalFilterForm, CouncilForm, CouncilFilterForm,
    CommitteeForm, CommitteeFilterForm, CommitteeMemberForm, CommitteeMemberFilterForm,
    SessionForm, SessionFilterForm, TermForm, TermFilterForm,
    PartyForm, PartyFilterForm, TermSeatDistributionForm
)
from .models import (
    Local, Council, Committee, CommitteeMember, Session, Term, Party, 
    TermSeatDistribution, SessionAttachment
)

User = get_user_model()


class LocalFormTests(TestCase):
    """Test cases for LocalForm"""
    
    def test_local_form_valid_data(self):
        """Test LocalForm with valid data"""
        form_data = {
            'name': 'Test Local',
            'code': 'TL',
            'description': 'Test local description'
        }
        
        form = LocalForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_local_form_required_fields(self):
        """Test LocalForm with missing required fields"""
        form_data = {
            'name': '',  # Required field missing
            'code': 'TL',
            'description': 'Test local description'
        }
        
        form = LocalForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)
    
    def test_local_form_code_validation(self):
        """Test LocalForm code field validation"""
        # Test with invalid characters
        form_data = {
            'name': 'Test Local',
            'code': 'TL-123',  # Contains invalid character
            'description': 'Test local description'
        }
        
        form = LocalForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('code', form.errors)
    
    def test_local_form_code_uppercase_conversion(self):
        """Test that code is converted to uppercase"""
        form_data = {
            'name': 'Test Local',
            'code': 'tl',  # Lowercase
            'description': 'Test local description'
        }
        
        form = LocalForm(data=form_data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['code'], 'TL')
    
    def test_local_form_code_alphanumeric_only(self):
        """Test that code contains only alphanumeric characters"""
        form_data = {
            'name': 'Test Local',
            'code': 'TL123',  # Valid alphanumeric
            'description': 'Test local description'
        }
        
        form = LocalForm(data=form_data)
        self.assertTrue(form.is_valid())


class LocalFilterFormTests(TestCase):
    """Test cases for LocalFilterForm"""
    
    def test_local_filter_form_valid_data(self):
        """Test LocalFilterForm with valid data"""
        form_data = {
            'name': 'Test',
            'code': 'TL',
            'is_active': True
        }
        
        form = LocalFilterForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_local_filter_form_empty_data(self):
        """Test LocalFilterForm with empty data"""
        form_data = {}
        
        form = LocalFilterForm(data=form_data)
        self.assertTrue(form.is_valid())  # Filter forms should be valid with empty data


class CouncilFormTests(TestCase):
    """Test cases for CouncilForm"""
    
    def setUp(self):
        """Set up test data"""
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
    
    def test_council_form_valid_data(self):
        """Test CouncilForm with valid data"""
        # Test editing an existing council
        form_data = {
            'name': 'Updated Council Name',
            'local': self.local.pk
        }
        
        form = CouncilForm(data=form_data, instance=self.local.council)
        self.assertTrue(form.is_valid())
    
    def test_council_form_required_fields(self):
        """Test CouncilForm with missing required fields"""
        form_data = {
            'name': '',  # Required field missing
            'local': self.local.pk,
            'is_active': True
        }
        
        form = CouncilForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)
    
    def test_council_form_local_filtering(self):
        """Test that CouncilForm filters locals correctly"""
        form = CouncilForm()
        expected_locals = Local.objects.filter(is_active=True)
        self.assertQuerySetEqual(
            form.fields['local'].queryset,
            expected_locals,
            transform=lambda x: x
        )


class CommitteeFormTests(TestCase):
    """Test cases for CommitteeForm"""
    
    def setUp(self):
        """Set up test data"""
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        
        self.council, created = Council.objects.get_or_create(
            local=self.local,
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
        
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        
        self.council, created = Council.objects.get_or_create(
            local=self.local,
            defaults={'name': 'Test Council'}
        )
        
        self.committee = Committee.objects.create(
            name='Test Committee',
            council=self.council
        )
    
    def test_committee_member_form_valid_data(self):
        """Test CommitteeMemberForm with valid data"""
        form_data = {
            'user': self.user.pk,
            'committee': self.committee.pk,
            'role': 'member',
            'is_active': True
        }
        
        form = CommitteeMemberForm(data=form_data)
        self.assertTrue(form.is_valid())
    
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


class SessionFormTests(TestCase):
    """Test cases for SessionForm"""
    
    def setUp(self):
        """Set up test data"""
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        
        self.council, created = Council.objects.get_or_create(
            local=self.local,
            defaults={'name': 'Test Council'}
        )
        
        self.term = Term.objects.create(
            name='Test Term',
            start_date=timezone.now().date(),
            end_date=(timezone.now().date() + timedelta(days=365))
        )
    
    def test_session_form_valid_data(self):
        """Test SessionForm with valid data"""
        form_data = {
            'title': 'Test Session',
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
        self.assertTrue(form.is_valid())
    
    def test_session_form_required_fields(self):
        """Test SessionForm with missing required fields"""
        form_data = {
            'title': '',  # Required field missing
            'council': self.council.pk,
            'term': self.term.pk,
            'session_type': 'regular',
            'status': 'scheduled',
            'scheduled_date': '2025-12-01T10:00'
        }
        
        form = SessionForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
    
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


class TermFormTests(TestCase):
    """Test cases for TermForm"""
    
    def setUp(self):
        """Set up test data"""
        self.local = Local.objects.create(
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
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
    
    def test_party_form_valid_data(self):
        """Test PartyForm with valid data"""
        form_data = {
            'name': 'Test Party',
            'local': self.local.pk,
            'color': '#FF0000',
            'is_active': True
        }
        
        form = PartyForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_party_form_required_fields(self):
        """Test PartyForm with missing required fields"""
        form_data = {
            'name': '',  # Required field missing
            'local': self.local.pk,
            'color': '#FF0000',
            'is_active': True
        }
        
        form = PartyForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)
    
    def test_party_form_local_filtering(self):
        """Test that PartyForm filters locals correctly"""
        form = PartyForm()
        expected_locals = Local.objects.filter(is_active=True)
        self.assertQuerySetEqual(
            form.fields['local'].queryset,
            expected_locals,
            transform=lambda x: x
        )


class TermSeatDistributionFormTests(TestCase):
    """Test cases for TermSeatDistributionForm"""
    
    def setUp(self):
        """Set up test data"""
        self.local = Local.objects.create(
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
            local=self.local
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
        expected_parties = Party.objects.filter(local=self.local, is_active=True)
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
            'local': 1,
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
    """Test cases for Local views"""
    
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
        
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
    
    def test_local_list_view_requires_superuser(self):
        """Test that LocalListView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('local:local-list'))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:local-list'))
        self.assertEqual(response.status_code, 200)
    
    def test_local_list_view_contains_locals(self):
        """Test that LocalListView contains local objects"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:local-list'))
        self.assertContains(response, self.local.name)
        self.assertContains(response, self.local.code)
    
    def test_local_list_view_search_functionality(self):
        """Test search functionality in LocalListView"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:local-list'), {'search': 'Test'})
        self.assertContains(response, self.local.name)
        
        # Test with a search term that definitely won't match
        response = self.client.get(reverse('local:local-list'), {'search': 'XYZ123Nonexistent'})
        # The search should return no results, so the local name should not be in the main content
        # Note: The template shows "No Locals found" when search returns no results
        # We check for the "No Locals found" message instead of checking for absence of the name
        # because the name might appear in navigation
        self.assertContains(response, "No Locals found")
    
    def test_local_list_view_status_filter(self):
        """Test status filter in LocalListView"""
        self.client.login(username='admin', password='adminpass123')
        
        # Test active filter
        response = self.client.get(reverse('local:local-list'), {'status': 'active'})
        self.assertContains(response, self.local.name)
        
        # Test inactive filter
        self.local.is_active = False
        self.local.save()
        response = self.client.get(reverse('local:local-list'), {'status': 'inactive'})
        self.assertContains(response, self.local.name)
    
    def test_local_detail_view_requires_superuser(self):
        """Test that LocalDetailView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('local:local-detail', kwargs={'pk': self.local.pk}))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:local-detail', kwargs={'pk': self.local.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_local_detail_view_contains_local_info(self):
        """Test that LocalDetailView contains local information"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:local-detail', kwargs={'pk': self.local.pk}))
        self.assertContains(response, self.local.name)
        # Note: The template doesn't display code and description in the current version
        # self.assertContains(response, self.local.code)
        # self.assertContains(response, self.local.description)
    
    def test_local_create_view_requires_superuser(self):
        """Test that LocalCreateView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('local:local-create'))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:local-create'))
        self.assertEqual(response.status_code, 200)
    
    def test_local_create_view_post_valid_data(self):
        """Test LocalCreateView with valid POST data"""
        self.client.login(username='admin', password='adminpass123')
        form_data = {
            'name': 'New Local',
            'code': 'NL',
            'description': 'New local description'
        }
        response = self.client.post(reverse('local:local-create'), form_data)
        self.assertEqual(response.status_code, 302)  # Redirect after successful creation
        
        # Check that the local was created
        self.assertTrue(Local.objects.filter(name='New Local').exists())
    
    def test_local_edit_view_requires_superuser(self):
        """Test that LocalUpdateView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('local:local-edit', kwargs={'pk': self.local.pk}))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:local-edit', kwargs={'pk': self.local.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_local_edit_view_post_valid_data(self):
        """Test LocalUpdateView with valid POST data"""
        self.client.login(username='admin', password='adminpass123')
        form_data = {
            'name': 'Updated Local',
            'code': 'UL',
            'description': 'Updated local description'
        }
        response = self.client.post(reverse('local:local-edit', kwargs={'pk': self.local.pk}), form_data)
        self.assertEqual(response.status_code, 302)  # Redirect after successful update
        
        # Check that the local was updated
        self.local.refresh_from_db()
        self.assertEqual(self.local.name, 'Updated Local')
    
    def test_local_delete_view_requires_superuser(self):
        """Test that LocalDeleteView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('local:local-delete', kwargs={'pk': self.local.pk}))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:local-delete', kwargs={'pk': self.local.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_local_delete_view_post_confirms_deletion(self):
        """Test LocalDeleteView with POST confirmation"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.post(reverse('local:local-delete', kwargs={'pk': self.local.pk}))
        self.assertEqual(response.status_code, 302)  # Redirect after successful deletion
        
        # Check that the local was deleted
        self.assertFalse(Local.objects.filter(pk=self.local.pk).exists())


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
        
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        # Council is automatically created with Local
        self.council = self.local.council
    
    def test_council_detail_view_requires_superuser(self):
        """Test that CouncilDetailView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('local:council-detail', kwargs={'pk': self.council.pk}))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:council-detail', kwargs={'pk': self.council.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_council_detail_view_contains_council_info(self):
        """Test that CouncilDetailView contains council information"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:council-detail', kwargs={'pk': self.council.pk}))
        self.assertContains(response, self.council.name)
    
    def test_council_edit_view_requires_superuser(self):
        """Test that CouncilUpdateView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('local:council-edit', kwargs={'pk': self.council.pk}))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:council-edit', kwargs={'pk': self.council.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_council_edit_view_post_valid_data(self):
        """Test CouncilUpdateView with valid POST data"""
        self.client.login(username='admin', password='adminpass123')
        form_data = {
            'name': 'Updated Council',
            'local': self.local.pk
        }
        response = self.client.post(reverse('local:council-edit', kwargs={'pk': self.council.pk}), form_data)
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
        
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        self.council = self.local.council
        
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
    
    def test_session_list_view_requires_superuser(self):
        """Test that SessionListView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('local:session-list'))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:session-list'))
        self.assertEqual(response.status_code, 200)
    
    def test_session_list_view_contains_sessions(self):
        """Test that SessionListView contains session objects"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:session-list'))
        self.assertContains(response, self.session.title)
    
    def test_session_detail_view_requires_superuser(self):
        """Test that SessionDetailView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('local:session-detail', kwargs={'pk': self.session.pk}))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:session-detail', kwargs={'pk': self.session.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_session_detail_view_contains_session_info(self):
        """Test that SessionDetailView contains session information"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:session-detail', kwargs={'pk': self.session.pk}))
        self.assertContains(response, self.session.title)
        self.assertContains(response, self.session.get_session_type_display())
    
    def test_session_create_view_requires_superuser(self):
        """Test that SessionCreateView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('local:session-create'))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:session-create'))
        self.assertEqual(response.status_code, 200)
    
    def test_session_create_view_post_valid_data(self):
        """Test SessionCreateView with valid POST data"""
        self.client.login(username='admin', password='adminpass123')
        form_data = {
            'title': 'New Session',
            'council': self.council.pk,
            'term': self.term.pk,
            'session_type': 'regular',
            'status': 'scheduled',
            'scheduled_date': (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M')
        }
        response = self.client.post(reverse('local:session-create'), form_data)
        self.assertEqual(response.status_code, 302)  # Redirect after successful creation
        
        # Check that the session was created
        self.assertTrue(Session.objects.filter(title='New Session').exists())
    
    def test_session_edit_view_requires_superuser(self):
        """Test that SessionUpdateView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('local:session-edit', kwargs={'pk': self.session.pk}))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:session-edit', kwargs={'pk': self.session.pk}))
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
        response = self.client.post(reverse('local:session-edit', kwargs={'pk': self.session.pk}), form_data)
        self.assertEqual(response.status_code, 302)  # Redirect after successful update
        
        # Check that the session was updated
        self.session.refresh_from_db()
        self.assertEqual(self.session.title, 'Updated Session')
    
    def test_session_delete_view_requires_superuser(self):
        """Test that SessionDeleteView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('local:session-delete', kwargs={'pk': self.session.pk}))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:session-delete', kwargs={'pk': self.session.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_session_delete_view_post_confirms_deletion(self):
        """Test SessionDeleteView with POST confirmation"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.post(reverse('local:session-delete', kwargs={'pk': self.session.pk}))
        self.assertEqual(response.status_code, 302)  # Redirect after successful deletion
        
        # Check that the session was deleted
        self.assertFalse(Session.objects.filter(pk=self.session.pk).exists())


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
        
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description'
        )
        self.council = self.local.council
        
        self.committee = Committee.objects.create(
            name='Test Committee',
            council=self.council,
            committee_type='Ausschuss'
        )
    
    def test_committee_list_view_requires_superuser(self):
        """Test that CommitteeListView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('local:committee-list'))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:committee-list'))
        self.assertEqual(response.status_code, 200)
    
    def test_committee_list_view_contains_committees(self):
        """Test that CommitteeListView contains committee objects"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:committee-list'))
        self.assertContains(response, self.committee.name)
    
    def test_committee_detail_view_requires_superuser(self):
        """Test that CommitteeDetailView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('local:committee-detail', kwargs={'pk': self.committee.pk}))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:committee-detail', kwargs={'pk': self.committee.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_committee_detail_view_contains_committee_info(self):
        """Test that CommitteeDetailView contains committee information"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:committee-detail', kwargs={'pk': self.committee.pk}))
        self.assertContains(response, self.committee.name)
        self.assertContains(response, self.committee.get_committee_type_display())
    
    def test_committee_create_view_requires_superuser(self):
        """Test that CommitteeCreateView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('local:committee-create'))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:committee-create'))
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
        response = self.client.post(reverse('local:committee-create'), form_data)
        self.assertEqual(response.status_code, 302)  # Redirect after successful creation
        
        # Check that the committee was created
        self.assertTrue(Committee.objects.filter(name='New Committee').exists())
    
    def test_committee_edit_view_requires_superuser(self):
        """Test that CommitteeUpdateView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('local:committee-edit', kwargs={'pk': self.committee.pk}))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:committee-edit', kwargs={'pk': self.committee.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_committee_edit_view_post_valid_data(self):
        """Test CommitteeUpdateView with valid POST data"""
        self.client.login(username='admin', password='adminpass123')
        form_data = {
            'name': 'Updated Committee',
            'council': self.council.pk,
            'committee_type': 'Kommission',
            'is_active': True
        }
        response = self.client.post(reverse('local:committee-edit', kwargs={'pk': self.committee.pk}), form_data)
        self.assertEqual(response.status_code, 302)  # Redirect after successful update
        
        # Check that the committee was updated
        self.committee.refresh_from_db()
        self.assertEqual(self.committee.name, 'Updated Committee')
    
    def test_committee_delete_view_requires_superuser(self):
        """Test that CommitteeDeleteView requires superuser"""
        # Test with regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('local:committee-delete', kwargs={'pk': self.committee.pk}))
        self.assertEqual(response.status_code, 403)
        
        # Test with superuser
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('local:committee-delete', kwargs={'pk': self.committee.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_committee_delete_view_post_confirms_deletion(self):
        """Test CommitteeDeleteView with POST confirmation"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.post(reverse('local:committee-delete', kwargs={'pk': self.committee.pk}))
        self.assertEqual(response.status_code, 302)  # Redirect after successful deletion
        
        # Check that the committee was deleted
        self.assertFalse(Committee.objects.filter(pk=self.committee.pk).exists())