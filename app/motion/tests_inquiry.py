from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta

from .forms import InquiryForm
from .models import Inquiry
from local.models import Local, Council, Session, Term, Party
from group.models import Group

User = get_user_model()


class InquiryFormTests(TestCase):
    """Test cases for InquiryForm"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test data
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
        
        self.session = Session.objects.create(
            title='Test Session',
            council=self.council,
            term=self.term,
            scheduled_date=timezone.now() + timedelta(days=1)
        )
        
        self.party = Party.objects.create(
            name='Test Party',
            local=self.local
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            party=self.party
        )
        
        # Create group membership for the user
        from group.models import GroupMember
        GroupMember.objects.create(
            user=self.user,
            group=self.group
        )
    
    def test_inquiry_form_valid_data(self):
        """Test InquiryForm with valid data"""
        form_data = {
            'title': 'Test Inquiry',
            'text': 'This is a test inquiry',
            'status': 'draft',
            'session': self.session.pk,
            'group': self.group.pk,
            'parties': [self.party.pk]
        }
        
        form = InquiryForm(data=form_data, user=self.user)
        self.assertTrue(form.is_valid())
    
    def test_inquiry_form_required_fields(self):
        """Test InquiryForm with missing required fields"""
        form_data = {
            'title': '',  # Required field missing
            'text': 'This is a test inquiry',
        }
        
        form = InquiryForm(data=form_data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
    
    def test_inquiry_form_initial_status(self):
        """Test that InquiryForm sets initial status to draft"""
        form = InquiryForm(user=self.user)
        self.assertEqual(form.fields['status'].initial, 'draft')
    
    def test_inquiry_form_group_field_hidden(self):
        """Test that InquiryForm hides group field"""
        form = InquiryForm(user=self.user)
        # Group field should be hidden
        self.assertEqual(form.fields['group'].widget.__class__.__name__, 'HiddenInput')
        self.assertIsNotNone(form.fields['group'].queryset)
        # Should have a default value set
        self.assertIsNotNone(form.fields['group'].initial)


class InquiryListViewTests(TestCase):
    """Test cases for InquiryListView"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        # Create test data
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description',
            is_active=True
        )
        
        self.council, created = Council.objects.get_or_create(
            local=self.local,
            defaults={'name': 'Test Council', 'is_active': True}
        )
        
        self.term = Term.objects.create(
            name='Test Term',
            start_date=timezone.now().date(),
            end_date=(timezone.now().date() + timedelta(days=365))
        )
        
        self.session = Session.objects.create(
            title='Test Session',
            council=self.council,
            term=self.term,
            scheduled_date=timezone.now() + timedelta(days=1),
            is_active=True
        )
        
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
        
        self.inquiry = Inquiry.objects.create(
            title='Test Inquiry',
            text='Test inquiry text',
            session=self.session,
            group=self.group,
            submitted_by=self.superuser,
            status='submitted'
        )
    
    def test_inquiry_list_view_superuser_access(self):
        """Test that superuser can view inquiry list"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('inquiry:inquiry-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Inquiry')
    
    def test_inquiry_list_view_template_used(self):
        """Test that inquiry list view uses correct template"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('inquiry:inquiry-list'))
        self.assertTemplateUsed(response, 'motion/inquiry_list.html')
    
    def test_inquiry_list_view_filters_by_status(self):
        """Test that inquiry list view filters by status"""
        # Create another inquiry with different status
        Inquiry.objects.create(
            title='Draft Inquiry',
            text='Draft inquiry text',
            session=self.session,
            group=self.group,
            submitted_by=self.superuser,
            status='draft'
        )
        
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('inquiry:inquiry-list') + '?status=submitted')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Inquiry')
        self.assertNotContains(response, 'Draft Inquiry')
    
    def test_inquiry_list_view_filters_by_session(self):
        """Test that inquiry list view filters by session"""
        # Create another session and inquiry
        session2 = Session.objects.create(
            title='Test Session 2',
            council=self.council,
            term=self.term,
            scheduled_date=timezone.now() + timedelta(days=2),
            is_active=True
        )
        
        Inquiry.objects.create(
            title='Inquiry in Session 2',
            text='Inquiry text',
            session=session2,
            group=self.group,
            submitted_by=self.superuser,
            status='submitted'
        )
        
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('inquiry:inquiry-list') + f'?session={self.session.pk}')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Inquiry')
        self.assertNotContains(response, 'Inquiry in Session 2')


class InquiryDetailViewTests(TestCase):
    """Test cases for InquiryDetailView"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        # Create test data
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description',
            is_active=True
        )
        
        self.council, created = Council.objects.get_or_create(
            local=self.local,
            defaults={'name': 'Test Council', 'is_active': True}
        )
        
        self.term = Term.objects.create(
            name='Test Term',
            start_date=timezone.now().date(),
            end_date=(timezone.now().date() + timedelta(days=365))
        )
        
        self.session = Session.objects.create(
            title='Test Session',
            council=self.council,
            term=self.term,
            scheduled_date=timezone.now() + timedelta(days=1),
            is_active=True
        )
        
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
        
        self.inquiry = Inquiry.objects.create(
            title='Test Inquiry',
            text='Test inquiry text',
            session=self.session,
            group=self.group,
            submitted_by=self.superuser,
            status='submitted'
        )
    
    def test_inquiry_detail_view_superuser_access(self):
        """Test that superuser can view inquiry detail"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('inquiry:inquiry-detail', kwargs={'pk': self.inquiry.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Inquiry')
        self.assertContains(response, 'Test inquiry text')
    
    def test_inquiry_detail_view_template_used(self):
        """Test that inquiry detail view uses correct template"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('inquiry:inquiry-detail', kwargs={'pk': self.inquiry.pk}))
        self.assertTemplateUsed(response, 'motion/inquiry_detail.html')
    
    def test_inquiry_detail_view_displays_parties(self):
        """Test that inquiry detail view displays supporting parties"""
        self.inquiry.parties.add(self.party)
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('inquiry:inquiry-detail', kwargs={'pk': self.inquiry.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Party')
    
    def test_inquiry_detail_view_displays_interventions(self):
        """Test that inquiry detail view displays interventions"""
        self.inquiry.interventions.add(self.superuser)
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('inquiry:inquiry-detail', kwargs={'pk': self.inquiry.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Wortmeldung')


class InquiryCreateViewTests(TestCase):
    """Test cases for InquiryCreateView"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        # Create test data
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description',
            is_active=True
        )
        
        self.council, created = Council.objects.get_or_create(
            local=self.local,
            defaults={'name': 'Test Council', 'is_active': True}
        )
        
        self.term = Term.objects.create(
            name='Test Term',
            start_date=timezone.now().date(),
            end_date=(timezone.now().date() + timedelta(days=365))
        )
        
        self.session = Session.objects.create(
            title='Test Session',
            council=self.council,
            term=self.term,
            scheduled_date=timezone.now() + timedelta(days=7),
            is_active=True
        )
        
        self.party = Party.objects.create(
            name='Test Party',
            local=self.local,
            color='#FF0000',
            is_active=True
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            party=self.party,
            is_active=True
        )
    
    def test_inquiry_create_redirects_to_session_detail(self):
        """Test that inquiry creation redirects to session detail page"""
        self.client.login(username='admin', password='adminpass123')
        
        # Create inquiry data
        inquiry_data = {
            'title': 'Test Inquiry',
            'text': 'Test inquiry text',
            'status': 'draft',
            'session': self.session.pk,
            'group': self.group.pk,
            'parties': []
        }
        
        # Submit inquiry creation form
        response = self.client.post(reverse('inquiry:inquiry-create'), inquiry_data)
        
        # Should redirect to session detail page
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('local:session-detail', kwargs={'pk': self.session.pk}))
        
        # Check that inquiry was created
        self.assertTrue(Inquiry.objects.filter(title='Test Inquiry', session=self.session).exists())
    
    def test_inquiry_create_with_session_parameter(self):
        """Test that inquiry creation works with session parameter in URL"""
        self.client.login(username='admin', password='adminpass123')
        
        # Create inquiry data
        inquiry_data = {
            'title': 'Test Inquiry',
            'text': 'Test inquiry text',
            'status': 'draft',
            'session': self.session.pk,
            'group': self.group.pk,
            'parties': []
        }
        
        # Submit inquiry creation form with session parameter
        response = self.client.post(f"{reverse('inquiry:inquiry-create')}?session={self.session.pk}", inquiry_data)
        
        # Should redirect to session detail page
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('local:session-detail', kwargs={'pk': self.session.pk}))
        
        # Check that inquiry was created with the correct session
        inquiry = Inquiry.objects.get(title='Test Inquiry')
        self.assertEqual(inquiry.session, self.session)
    
    def test_inquiry_create_form_with_session_parameter_shows_session_info(self):
        """Test that inquiry create form shows session information when session parameter is provided"""
        self.client.login(username='admin', password='adminpass123')
        
        # Get the form page with session parameter
        response = self.client.get(f"{reverse('inquiry:inquiry-create')}?session={self.session.pk}")
        
        self.assertEqual(response.status_code, 200)
        # Check that the form contains session information
        self.assertContains(response, self.session.title)
        self.assertContains(response, self.session.council.name)
        # Check that the session field is hidden (value should be present)
        self.assertContains(response, f'value="{self.session.pk}"')
    
    def test_inquiry_create_form_without_session_parameter_shows_select(self):
        """Test that inquiry create form shows session select when no session parameter is provided"""
        self.client.login(username='admin', password='adminpass123')
        
        # Get the form page without session parameter
        response = self.client.get(reverse('inquiry:inquiry-create'))
        
        self.assertEqual(response.status_code, 200)
        # Check that the form contains session select field
        self.assertContains(response, 'form-select')
    
    def test_inquiry_create_template_used(self):
        """Test that inquiry create view uses correct template"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('inquiry:inquiry-create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'motion/inquiry_form.html')
    
    def test_inquiry_create_sets_submitted_by(self):
        """Test that inquiry creation sets submitted_by to current user"""
        self.client.login(username='admin', password='adminpass123')
        
        inquiry_data = {
            'title': 'Test Inquiry',
            'text': 'Test inquiry text',
            'status': 'draft',
            'session': self.session.pk,
            'group': self.group.pk,
            'parties': []
        }
        
        response = self.client.post(reverse('inquiry:inquiry-create'), inquiry_data)
        self.assertEqual(response.status_code, 302)
        
        inquiry = Inquiry.objects.get(title='Test Inquiry')
        self.assertEqual(inquiry.submitted_by, self.superuser)


class InquiryUpdateViewTests(TestCase):
    """Test cases for InquiryUpdateView"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        # Create test data
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description',
            is_active=True
        )
        
        self.council, created = Council.objects.get_or_create(
            local=self.local,
            defaults={'name': 'Test Council', 'is_active': True}
        )
        
        self.term = Term.objects.create(
            name='Test Term',
            start_date=timezone.now().date(),
            end_date=(timezone.now().date() + timedelta(days=365))
        )
        
        self.session = Session.objects.create(
            title='Test Session',
            council=self.council,
            term=self.term,
            scheduled_date=timezone.now() + timedelta(days=1),
            is_active=True
        )
        
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
        
        self.inquiry = Inquiry.objects.create(
            title='Test Inquiry',
            text='Test inquiry text',
            session=self.session,
            group=self.group,
            submitted_by=self.superuser,
            status='draft'
        )
    
    def test_inquiry_update_view_superuser_access(self):
        """Test that superuser can access inquiry update view"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('inquiry:inquiry-edit', kwargs={'pk': self.inquiry.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Inquiry')
    
    def test_inquiry_update_redirects_to_detail(self):
        """Test that inquiry update redirects to inquiry detail page"""
        self.client.login(username='admin', password='adminpass123')
        
        inquiry_data = {
            'title': 'Updated Inquiry',
            'text': 'Updated inquiry text',
            'status': 'draft',
            'session': self.session.pk,
            'group': self.group.pk,
            'parties': []
        }
        
        response = self.client.post(reverse('inquiry:inquiry-edit', kwargs={'pk': self.inquiry.pk}), inquiry_data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('inquiry:inquiry-detail', kwargs={'pk': self.inquiry.pk}))
        
        # Check that inquiry was updated
        self.inquiry.refresh_from_db()
        self.assertEqual(self.inquiry.title, 'Updated Inquiry')
    
    def test_inquiry_update_template_used(self):
        """Test that inquiry update view uses correct template"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('inquiry:inquiry-edit', kwargs={'pk': self.inquiry.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'motion/inquiry_form.html')


class InquiryDeleteViewTests(TestCase):
    """Test cases for InquiryDeleteView"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        # Create test data
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description',
            is_active=True
        )
        
        self.council, created = Council.objects.get_or_create(
            local=self.local,
            defaults={'name': 'Test Council', 'is_active': True}
        )
        
        self.term = Term.objects.create(
            name='Test Term',
            start_date=timezone.now().date(),
            end_date=(timezone.now().date() + timedelta(days=365))
        )
        
        self.session = Session.objects.create(
            title='Test Session',
            council=self.council,
            term=self.term,
            scheduled_date=timezone.now() + timedelta(days=1),
            is_active=True
        )
        
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
        
        self.inquiry = Inquiry.objects.create(
            title='Test Inquiry',
            text='Test inquiry text',
            session=self.session,
            group=self.group,
            submitted_by=self.superuser,
            status='draft'
        )
    
    def test_inquiry_delete_view_superuser_access(self):
        """Test that superuser can access inquiry delete view"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('inquiry:inquiry-delete', kwargs={'pk': self.inquiry.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Inquiry')
    
    def test_inquiry_delete_template_used(self):
        """Test that inquiry delete view uses correct template"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('inquiry:inquiry-delete', kwargs={'pk': self.inquiry.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'motion/inquiry_confirm_delete.html')
    
    def test_inquiry_delete_actually_deletes(self):
        """Test that inquiry delete actually deletes the inquiry"""
        self.client.login(username='admin', password='adminpass123')
        
        inquiry_pk = self.inquiry.pk
        response = self.client.post(reverse('inquiry:inquiry-delete', kwargs={'pk': self.inquiry.pk}))
        
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Inquiry.objects.filter(pk=inquiry_pk).exists())
    
    def test_inquiry_delete_redirects_to_list(self):
        """Test that inquiry delete redirects to inquiry list"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.post(reverse('inquiry:inquiry-delete', kwargs={'pk': self.inquiry.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('inquiry:inquiry-list'))

