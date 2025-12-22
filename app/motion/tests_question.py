from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta

from .forms import QuestionForm
from .models import Question
from local.models import Local, Council, Session, Term, Party
from group.models import Group

User = get_user_model()


class QuestionFormTests(TestCase):
    """Test cases for QuestionForm"""
    
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
    
    def test_question_form_valid_data(self):
        """Test QuestionForm with valid data"""
        form_data = {
            'title': 'Test Question',
            'text': 'This is a test question',
            'status': 'draft',
            'session': self.session.pk,
            'group': self.group.pk,
            'parties': [self.party.pk]
        }
        
        form = QuestionForm(data=form_data, user=self.user)
        self.assertTrue(form.is_valid())
    
    def test_question_form_required_fields(self):
        """Test QuestionForm with missing required fields"""
        form_data = {
            'title': '',  # Required field missing
            'text': 'This is a test question',
        }
        
        form = QuestionForm(data=form_data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
    
    def test_question_form_initial_status(self):
        """Test that QuestionForm sets initial status to draft"""
        form = QuestionForm(user=self.user)
        self.assertEqual(form.fields['status'].initial, 'draft')
    
    def test_question_form_group_field_hidden(self):
        """Test that QuestionForm hides group field"""
        form = QuestionForm(user=self.user)
        # Group field should be hidden
        self.assertEqual(form.fields['group'].widget.__class__.__name__, 'HiddenInput')
        self.assertIsNotNone(form.fields['group'].queryset)
        # Should have a default value set
        self.assertIsNotNone(form.fields['group'].initial)


class QuestionListViewTests(TestCase):
    """Test cases for QuestionListView"""
    
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
        
        self.question = Question.objects.create(
            title='Test Question',
            text='Test question text',
            session=self.session,
            group=self.group,
            submitted_by=self.superuser,
            status='submitted'
        )
    
    def test_question_list_view_superuser_access(self):
        """Test that superuser can view question list"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('question:question-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Question')
    
    def test_question_list_view_template_used(self):
        """Test that question list view uses correct template"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('question:question-list'))
        self.assertTemplateUsed(response, 'motion/question_list.html')
    
    def test_question_list_view_filters_by_status(self):
        """Test that question list view filters by status"""
        # Create another question with different status
        Question.objects.create(
            title='Draft Question',
            text='Draft question text',
            session=self.session,
            group=self.group,
            submitted_by=self.superuser,
            status='draft'
        )
        
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('question:question-list') + '?status=submitted')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Question')
        self.assertNotContains(response, 'Draft Question')
    
    def test_question_list_view_filters_by_session(self):
        """Test that question list view filters by session"""
        # Create another session and question
        session2 = Session.objects.create(
            title='Test Session 2',
            council=self.council,
            term=self.term,
            scheduled_date=timezone.now() + timedelta(days=2),
            is_active=True
        )
        
        Question.objects.create(
            title='Question in Session 2',
            text='Question text',
            session=session2,
            group=self.group,
            submitted_by=self.superuser,
            status='submitted'
        )
        
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('question:question-list') + f'?session={self.session.pk}')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Question')
        self.assertNotContains(response, 'Question in Session 2')


class QuestionDetailViewTests(TestCase):
    """Test cases for QuestionDetailView"""
    
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
        
        self.question = Question.objects.create(
            title='Test Question',
            text='Test question text',
            session=self.session,
            group=self.group,
            submitted_by=self.superuser,
            status='submitted'
        )
    
    def test_question_detail_view_superuser_access(self):
        """Test that superuser can view question detail"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('question:question-detail', kwargs={'pk': self.question.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Question')
        self.assertContains(response, 'Test question text')
    
    def test_question_detail_view_template_used(self):
        """Test that question detail view uses correct template"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('question:question-detail', kwargs={'pk': self.question.pk}))
        self.assertTemplateUsed(response, 'motion/question_detail.html')
    
    def test_question_detail_view_displays_parties(self):
        """Test that question detail view displays supporting parties"""
        self.question.parties.add(self.party)
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('question:question-detail', kwargs={'pk': self.question.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Party')
    
    def test_question_detail_view_displays_interventions(self):
        """Test that question detail view displays interventions"""
        self.question.interventions.add(self.superuser)
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('question:question-detail', kwargs={'pk': self.question.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Wortmeldung')


class QuestionCreateViewTests(TestCase):
    """Test cases for QuestionCreateView"""
    
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
    
    def test_question_create_redirects_to_session_detail(self):
        """Test that question creation redirects to session detail page"""
        self.client.login(username='admin', password='adminpass123')
        
        # Create question data
        question_data = {
            'title': 'Test Question',
            'text': 'Test question text',
            'status': 'draft',
            'session': self.session.pk,
            'group': self.group.pk,
            'parties': []
        }
        
        # Submit question creation form
        response = self.client.post(reverse('question:question-create'), question_data)
        
        # Should redirect to session detail page
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('local:session-detail', kwargs={'pk': self.session.pk}))
        
        # Check that question was created
        self.assertTrue(Question.objects.filter(title='Test Question', session=self.session).exists())
    
    def test_question_create_with_session_parameter(self):
        """Test that question creation works with session parameter in URL"""
        self.client.login(username='admin', password='adminpass123')
        
        # Create question data
        question_data = {
            'title': 'Test Question',
            'text': 'Test question text',
            'status': 'draft',
            'session': self.session.pk,
            'group': self.group.pk,
            'parties': []
        }
        
        # Submit question creation form with session parameter
        response = self.client.post(f"{reverse('question:question-create')}?session={self.session.pk}", question_data)
        
        # Should redirect to session detail page
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('local:session-detail', kwargs={'pk': self.session.pk}))
        
        # Check that question was created with the correct session
        question = Question.objects.get(title='Test Question')
        self.assertEqual(question.session, self.session)
    
    def test_question_create_form_with_session_parameter_shows_session_info(self):
        """Test that question create form shows session information when session parameter is provided"""
        self.client.login(username='admin', password='adminpass123')
        
        # Get the form page with session parameter
        response = self.client.get(f"{reverse('question:question-create')}?session={self.session.pk}")
        
        self.assertEqual(response.status_code, 200)
        # Check that the form contains session information
        self.assertContains(response, self.session.title)
        self.assertContains(response, self.session.council.name)
        # Check that the session field is hidden (value should be present)
        self.assertContains(response, f'value="{self.session.pk}"')
    
    def test_question_create_form_without_session_parameter_shows_select(self):
        """Test that question create form shows session select when no session parameter is provided"""
        self.client.login(username='admin', password='adminpass123')
        
        # Get the form page without session parameter
        response = self.client.get(reverse('question:question-create'))
        
        self.assertEqual(response.status_code, 200)
        # Check that the form contains session select field
        self.assertContains(response, 'form-select')
    
    def test_question_create_template_used(self):
        """Test that question create view uses correct template"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('question:question-create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'motion/question_form.html')
    
    def test_question_create_sets_submitted_by(self):
        """Test that question creation sets submitted_by to current user"""
        self.client.login(username='admin', password='adminpass123')
        
        question_data = {
            'title': 'Test Question',
            'text': 'Test question text',
            'status': 'draft',
            'session': self.session.pk,
            'group': self.group.pk,
            'parties': []
        }
        
        response = self.client.post(reverse('question:question-create'), question_data)
        self.assertEqual(response.status_code, 302)
        
        question = Question.objects.get(title='Test Question')
        self.assertEqual(question.submitted_by, self.superuser)


class QuestionUpdateViewTests(TestCase):
    """Test cases for QuestionUpdateView"""
    
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
        
        self.question = Question.objects.create(
            title='Test Question',
            text='Test question text',
            session=self.session,
            group=self.group,
            submitted_by=self.superuser,
            status='draft'
        )
    
    def test_question_update_view_superuser_access(self):
        """Test that superuser can access question update view"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('question:question-edit', kwargs={'pk': self.question.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Question')
    
    def test_question_update_redirects_to_detail(self):
        """Test that question update redirects to question detail page"""
        self.client.login(username='admin', password='adminpass123')
        
        question_data = {
            'title': 'Updated Question',
            'text': 'Updated question text',
            'status': 'draft',
            'session': self.session.pk,
            'group': self.group.pk,
            'parties': []
        }
        
        response = self.client.post(reverse('question:question-edit', kwargs={'pk': self.question.pk}), question_data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('question:question-detail', kwargs={'pk': self.question.pk}))
        
        # Check that question was updated
        self.question.refresh_from_db()
        self.assertEqual(self.question.title, 'Updated Question')
    
    def test_question_update_template_used(self):
        """Test that question update view uses correct template"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('question:question-edit', kwargs={'pk': self.question.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'motion/question_form.html')


class QuestionDeleteViewTests(TestCase):
    """Test cases for QuestionDeleteView"""
    
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
        
        self.question = Question.objects.create(
            title='Test Question',
            text='Test question text',
            session=self.session,
            group=self.group,
            submitted_by=self.superuser,
            status='draft'
        )
    
    def test_question_delete_view_superuser_access(self):
        """Test that superuser can access question delete view"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('question:question-delete', kwargs={'pk': self.question.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Question')
    
    def test_question_delete_template_used(self):
        """Test that question delete view uses correct template"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('question:question-delete', kwargs={'pk': self.question.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'motion/question_confirm_delete.html')
    
    def test_question_delete_actually_deletes(self):
        """Test that question delete actually deletes the question"""
        self.client.login(username='admin', password='adminpass123')
        
        question_pk = self.question.pk
        response = self.client.post(reverse('question:question-delete', kwargs={'pk': self.question.pk}))
        
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Question.objects.filter(pk=question_pk).exists())
    
    def test_question_delete_redirects_to_list(self):
        """Test that question delete redirects to question list"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.post(reverse('question:question-delete', kwargs={'pk': self.question.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('question:question-list'))

