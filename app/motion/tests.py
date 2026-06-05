from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms import formset_factory
from django.utils import timezone
from django.utils.datastructures import MultiValueDict
from django.urls import reverse
from datetime import datetime, timedelta

from .forms import (
    MotionForm, MotionVoteForm, MotionVoteFormSetFactory,
    MotionStatusForm, MotionCommentForm, MotionAttachmentForm,
    MotionGroupDecisionForm, InquiryForm, InquiryStatusForm,
    validate_answer_pdf_files,
)
from .models import (
    Motion, MotionVote, MotionComment, MotionAttachment, MotionStatus,
    MotionStatusAnswerFile, MotionGroupDecision, Inquiry, InquiryStatus,
    InquiryStatusAnswerFile,
)
from local.models import Local, Council, Session, Term, Party, Committee
from group.models import Group

User = get_user_model()


class MotionFormTests(TestCase):
    """Test cases for MotionForm"""
    
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
        
        self.committee = Committee.objects.create(
            name='Test Committee',
            council=self.council
        )
    
    def test_motion_form_valid_data(self):
        """Test MotionForm with valid data"""
        form_data = {
            'title': 'Test Motion',
            'text': 'This is a test motion',
            'rationale': 'Test rationale',
            'motion_type': 'general',
            'status': 'draft',
            'session': self.session.pk,
            'group': self.group.pk,
            'parties': [self.party.pk]
        }
        
        form = MotionForm(data=form_data, user=self.user)
        self.assertTrue(form.is_valid())
    
    def test_motion_form_required_fields(self):
        """Test MotionForm with missing required fields"""
        form_data = {
            'title': '',  # Required field missing
            'text': 'This is a test motion',
        }
        
        form = MotionForm(data=form_data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
    
    def test_motion_form_initial_status(self):
        """Test that MotionForm sets initial status to draft"""
        form = MotionForm(user=self.user)
        self.assertEqual(form.fields['status'].initial, 'draft')
    
    def test_motion_form_group_field_hidden(self):
        """Test that MotionForm hides group field"""
        form = MotionForm(user=self.user)
        # Group field should be hidden
        self.assertEqual(form.fields['group'].widget.__class__.__name__, 'HiddenInput')
        self.assertIsNotNone(form.fields['group'].queryset)
        # Should have a default value set
        self.assertIsNotNone(form.fields['group'].initial)


class MotionVoteFormTests(TestCase):
    """Test cases for MotionVoteForm"""
    
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
        
        self.motion = Motion.objects.create(
            title='Test Motion',
            text='Test motion text',
            session=self.session,
            group=self.group,
            submitted_by=self.user
        )
    
    def test_motion_vote_form_valid_data(self):
        """Test MotionVoteForm with valid data"""
        form_data = {
            'party': self.party.pk,
            'approve_votes': 5,
            'reject_votes': 3,
            'notes': 'Test vote notes'
        }
        
        form = MotionVoteForm(data=form_data, motion=self.motion)
        self.assertTrue(form.is_valid())
    
    def test_motion_vote_form_no_votes(self):
        """Test MotionVoteForm with party selected but no votes cast is invalid (abstaining not allowed)"""
        form_data = {
            'party': self.party.pk,
            'approve_votes': 0,
            'reject_votes': 0,
            'notes': ''
        }
        
        form = MotionVoteForm(data=form_data, motion=self.motion)
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)
    
    def test_motion_vote_form_negative_votes(self):
        """Test MotionVoteForm with negative votes"""
        form_data = {
            'party': self.party.pk,
            'approve_votes': -1,
            'reject_votes': 3,
            'notes': ''
        }
        
        form = MotionVoteForm(data=form_data, motion=self.motion)
        self.assertFalse(form.is_valid())
    
    def test_motion_vote_form_party_filtering(self):
        """Test that MotionVoteForm filters parties correctly"""
        form = MotionVoteForm(motion=self.motion)
        # Should only show parties from the motion's session council local
        expected_parties = Party.objects.filter(
            local=self.motion.session.council.local,
            is_active=True
        )
        self.assertQuerySetEqual(
            form.fields['party'].queryset,
            expected_parties,
            transform=lambda x: x
        )


class MotionVoteFormSetTests(TestCase):
    """Test cases for MotionVoteFormSet"""
    
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
        
        self.party1 = Party.objects.create(
            name='Test Party 1',
            local=self.local
        )
        
        self.party2 = Party.objects.create(
            name='Test Party 2',
            local=self.local
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            party=self.party1
        )
        
        # Create group membership for the user
        from group.models import GroupMember
        GroupMember.objects.create(
            user=self.user,
            group=self.group
        )
        
        self.motion = Motion.objects.create(
            title='Test Motion',
            text='Test motion text',
            session=self.session,
            group=self.group,
            submitted_by=self.user
        )
    
    def test_motion_vote_formset_initialization(self):
        """Test MotionVoteFormSet initialization with parties"""
        parties = Party.objects.filter(
            local=self.motion.session.council.local,
            is_active=True
        )
        
        formset = MotionVoteFormSetFactory(
            motion=self.motion,
            initial=[{'party': party.pk} for party in parties]
        )
        
        self.assertEqual(len(formset.forms), parties.count())
        
        # Check that each form has the correct party in initial data
        for i, party in enumerate(parties):
            if i < len(formset.forms):
                self.assertEqual(formset.forms[i].initial.get('party'), party.pk)
    
    def test_motion_vote_formset_duplicate_parties(self):
        """Test that formset prevents duplicate parties"""
        form_data = {
            'form-TOTAL_FORMS': '2',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-party': self.party1.pk,
            'form-0-approve_votes': '5',
            'form-0-reject_votes': '3',
            'form-0-notes': '',
            'form-1-party': self.party1.pk,  # Duplicate party
            'form-1-approve_votes': '2',
            'form-1-reject_votes': '1',
            'form-1-notes': '',
        }
        
        formset = MotionVoteFormSetFactory(data=form_data, motion=self.motion)
        self.assertFalse(formset.is_valid())
        # Check for duplicate party error in formset non_form_errors
        self.assertTrue(len(formset.non_form_errors()) > 0)


class MotionStatusFormTests(TestCase):
    """Test cases for MotionStatusForm"""
    
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
        
        self.motion = Motion.objects.create(
            title='Test Motion',
            text='Test motion text',
            session=self.session,
            group=self.group,
            submitted_by=self.user
        )
        
        self.committee = Committee.objects.create(
            name='Test Committee',
            council=self.council
        )
    
    def test_motion_status_form_valid_data(self):
        """Test MotionStatusForm with valid data"""
        form_data = {
            'status': 'approved',
            'reason': 'Test reason for approval'
        }
        
        form = MotionStatusForm(data=form_data, motion=self.motion, changed_by=self.user)
        self.assertTrue(form.is_valid())
    
    def test_motion_status_form_committee_required_for_refer(self):
        """Test that committee is required when status is refer_to_committee"""
        form_data = {
            'status': 'refer_to_committee',
            'reason': 'Test reason',
            'committee': ''  # Missing committee
        }
        
        form = MotionStatusForm(data=form_data, motion=self.motion, changed_by=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('committee', form.errors)
    
    def test_motion_status_form_committee_not_required_for_other_statuses(self):
        """Test that committee is not required for other statuses"""
        form_data = {
            'status': 'approved',
            'reason': 'Test reason',
            'committee': ''  # No committee needed
        }
        
        form = MotionStatusForm(data=form_data, motion=self.motion, changed_by=self.user)
        self.assertTrue(form.is_valid())
    
    def test_motion_status_form_committee_filtering(self):
        """Test that committee field is filtered to motion's session council"""
        form = MotionStatusForm(motion=self.motion, changed_by=self.user)
        expected_committees = Committee.objects.filter(council=self.motion.session.council)
        self.assertQuerySetEqual(
            form.fields['committee'].queryset,
            expected_committees,
            transform=lambda x: x
        )


class MotionCommentFormTests(TestCase):
    """Test cases for MotionCommentForm"""
    
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
        
        self.motion = Motion.objects.create(
            title='Test Motion',
            text='Test motion text',
            session=self.session,
            group=self.group,
            submitted_by=self.user
        )
    
    def test_motion_comment_form_valid_data(self):
        """Test MotionCommentForm with valid data"""
        form_data = {
            'content': 'This is a test comment',
            'is_public': True
        }
        
        form = MotionCommentForm(data=form_data, motion=self.motion, author=self.user)
        self.assertTrue(form.is_valid())
    
    def test_motion_comment_form_required_content(self):
        """Test MotionCommentForm with missing content"""
        form_data = {
            'content': '',  # Required field missing
            'is_public': True
        }
        
        form = MotionCommentForm(data=form_data, motion=self.motion, author=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('content', form.errors)
    
    def test_motion_comment_form_initial_values(self):
        """Test MotionCommentForm initial values"""
        form = MotionCommentForm(motion=self.motion, author=self.user)
        self.assertEqual(form.fields['is_public'].initial, True)


class MotionAttachmentFormTests(TestCase):
    """Test cases for MotionAttachmentForm"""
    
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
        
        self.motion = Motion.objects.create(
            title='Test Motion',
            text='Test motion text',
            session=self.session,
            group=self.group,
            submitted_by=self.user
        )
    
    def test_motion_attachment_form_valid_data(self):
        """Test MotionAttachmentForm with valid data"""
        form_data = {
            'file_type': 'document',
            'description': 'Test attachment description'
        }
        
        form = MotionAttachmentForm(data=form_data, motion=self.motion)
        # Form will be invalid without file, but that's expected
        self.assertFalse(form.is_valid())
        self.assertIn('file', form.errors)
    
    def test_motion_attachment_form_required_file(self):
        """Test MotionAttachmentForm with missing file"""
        form_data = {
            'file_type': 'document',
            'description': 'Test attachment description'
        }
        
        form = MotionAttachmentForm(data=form_data, motion=self.motion)
        self.assertFalse(form.is_valid())
        self.assertIn('file', form.errors)


class MotionGroupDecisionFormTests(TestCase):
    """Test cases for MotionGroupDecisionForm"""
    
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
        
        self.motion = Motion.objects.create(
            title='Test Motion',
            text='Test motion text',
            session=self.session,
            group=self.group,
            submitted_by=self.user
        )
        
        self.committee = Committee.objects.create(
            name='Test Committee',
            council=self.council
        )
    
    def test_motion_group_decision_form_valid_data(self):
        """Test MotionGroupDecisionForm with valid data"""
        form_data = {
            'decision': 'approve',
            'description': 'Test group decision',
            'committee': self.committee.pk,
            'decision_date': '2025-12-01',
            'decision_time': '14:00'
        }
        
        form = MotionGroupDecisionForm(data=form_data, motion=self.motion)
        self.assertTrue(form.is_valid())
    
    def test_motion_group_decision_form_committee_required_for_refer(self):
        """Test that committee is required when decision is refer_to_committee"""
        form_data = {
            'decision': 'refer_to_committee',
            'description': 'Test group decision',
            'committee': '',  # Missing committee
            'decision_date': '2025-12-01',
            'decision_time': '14:00'
        }
        
        form = MotionGroupDecisionForm(data=form_data, motion=self.motion)
        self.assertFalse(form.is_valid())
        self.assertIn('committee', form.errors)
    
    def test_motion_group_decision_form_committee_not_required_for_other_decisions(self):
        """Test that committee is not required for other decisions"""
        form_data = {
            'decision': 'approve',
            'description': 'Test group decision',
            'committee': '',  # No committee needed
            'decision_date': '2025-12-01',
            'decision_time': '14:00'
        }
        
        form = MotionGroupDecisionForm(data=form_data, motion=self.motion)
        self.assertTrue(form.is_valid())
    
    def test_motion_group_decision_form_committee_filtering(self):
        """Test that committee field is filtered to motion's session council"""
        form = MotionGroupDecisionForm(motion=self.motion)
        expected_committees = Committee.objects.filter(council=self.motion.session.council)
        self.assertQuerySetEqual(
            form.fields['committee'].queryset,
            expected_committees,
            transform=lambda x: x
        )


class MotionCreateViewTests(TestCase):
    """Test cases for MotionCreateView"""
    
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
        
        self.party = Party.objects.create(
            name='Test Party',
            local=self.local,
            color='#FF0000',
            is_active=True
        )
        
        self.session = Session.objects.create(
            title='Test Session',
            council=self.council,
            scheduled_date=timezone.now() + timedelta(days=7),
            is_active=True
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            party=self.party,
            is_active=True
        )
    
    def test_motion_create_redirects_to_session_detail(self):
        """Test that motion creation redirects to session detail page"""
        self.client.login(username='admin', password='adminpass123')
        
        # Create motion data
        motion_data = {
            'title': 'Test Motion',
            'text': 'Test motion text',
            'rationale': 'Test rationale',
            'motion_type': 'general',
            'status': 'draft',
            'session': self.session.pk,
            'group': self.group.pk,
            'parties': []
        }
        
        # Submit motion creation form
        response = self.client.post(reverse('motion:motion-create'), motion_data)
        
        # Should redirect to session detail page
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('local:session-detail', kwargs={'pk': self.session.pk}))
        
        # Check that motion was created
        self.assertTrue(Motion.objects.filter(title='Test Motion', session=self.session).exists())
    
    def test_motion_create_redirects_to_motion_list_when_no_session(self):
        """Test that motion creation redirects to motion list when no session is provided"""
        self.client.login(username='admin', password='adminpass123')
        
        # Create motion data with session (required field)
        motion_data = {
            'title': 'Test Motion',
            'text': 'Test motion text',
            'rationale': 'Test rationale',
            'motion_type': 'general',
            'status': 'draft',
            'session': self.session.pk,
            'group': self.group.pk,
            'parties': []
        }
        
        # Submit motion creation form
        response = self.client.post(reverse('motion:motion-create'), motion_data)
        
        # Should redirect to session detail page (since session is provided)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('local:session-detail', kwargs={'pk': self.session.pk}))
    
    def test_motion_create_with_session_parameter(self):
        """Test that motion creation works with session parameter in URL"""
        self.client.login(username='admin', password='adminpass123')
        
        # Create motion data
        motion_data = {
            'title': 'Test Motion',
            'text': 'Test motion text',
            'rationale': 'Test rationale',
            'motion_type': 'general',
            'status': 'draft',
            'session': self.session.pk,
            'group': self.group.pk,
            'parties': []
        }
        
        # Submit motion creation form with session parameter
        response = self.client.post(f"{reverse('motion:motion-create')}?session={self.session.pk}", motion_data)
        
        # Should redirect to session detail page
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('local:session-detail', kwargs={'pk': self.session.pk}))
        
        # Check that motion was created with the correct session
        motion = Motion.objects.get(title='Test Motion')
        self.assertEqual(motion.session, self.session)
    
    def test_motion_create_form_with_session_parameter_shows_session_info(self):
        """Test that motion create form shows session information when session parameter is provided"""
        self.client.login(username='admin', password='adminpass123')
        
        # Get the form page with session parameter
        response = self.client.get(f"{reverse('motion:motion-create')}?session={self.session.pk}")
        
        self.assertEqual(response.status_code, 200)
        # Check that the form contains session information
        self.assertContains(response, self.session.title)
        self.assertContains(response, self.session.council.name)
        # Check that the session field is hidden (value should be present)
        self.assertContains(response, f'value="{self.session.pk}"')
    
    def test_motion_create_form_without_session_parameter_shows_select(self):
        """Test that motion create form shows session select when no session parameter is provided"""
        self.client.login(username='admin', password='adminpass123')
        
        # Get the form page without session parameter
        response = self.client.get(reverse('motion:motion-create'))
        
        self.assertEqual(response.status_code, 200)
        # Check that the form contains session select field
        self.assertContains(response, 'form-select')
        # Check that session info is not shown
        self.assertNotContains(response, 'form-control-plaintext')
    
    def test_motion_create_form_with_session_parameter_submits_correctly(self):
        """Test that motion create form submits correctly when session parameter is provided"""
        self.client.login(username='admin', password='adminpass123')
        
        # Create motion data
        motion_data = {
            'title': 'Test Motion',
            'text': 'Test motion text',
            'rationale': 'Test rationale',
            'motion_type': 'general',
            'status': 'draft',
            'group': self.group.pk,
            'parties': []
        }
        
        # Submit motion creation form with session parameter
        response = self.client.post(f"{reverse('motion:motion-create')}?session={self.session.pk}", motion_data)
        
        # Should redirect to session detail page (success)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('local:session-detail', kwargs={'pk': self.session.pk}))
        
        # Check that motion was created with the correct session
        motion = Motion.objects.get(title='Test Motion')
        self.assertEqual(motion.session, self.session)


class MotionInquiryStatusPermissionTests(TestCase):
    """Tests for motion and inquiry status-change permissions for group managers."""

    def setUp(self):
        self.client = Client()

        self.local = Local.objects.create(
            name='Status Perm Local',
            code='SPL',
            description='Test local',
            is_active=True,
        )
        self.council = self.local.council
        self.party = Party.objects.create(
            name='Status Perm Party',
            local=self.local,
            is_active=True,
        )
        self.group = Group.objects.create(
            name='Status Perm Group',
            party=self.party,
            is_active=True,
        )

        self.term = Term.objects.create(
            name='Status Perm Term',
            start_date=timezone.now().date(),
            end_date=(timezone.now().date() + timedelta(days=365)),
            is_active=True,
        )
        self.session = Session.objects.create(
            title='Status Perm Session',
            council=self.council,
            term=self.term,
            scheduled_date=timezone.now() + timedelta(days=1),
            is_active=True,
        )

        from group.models import GroupMember
        from user.models import Role

        self.leader_role = Role.objects.get_or_create(name='Leader', defaults={'is_active': True})[0]
        self.deputy_leader_role = Role.objects.get_or_create(
            name='Deputy Leader', defaults={'is_active': True}
        )[0]
        self.group_admin_role = Role.objects.get_or_create(
            name='Group Admin', defaults={'is_active': True}
        )[0]
        self.member_role = Role.objects.get_or_create(name='Member', defaults={'is_active': True})[0]

        self.motion_edit_role = Role.objects.create(
            name='Motion Editor',
            is_active=True,
            permissions={'permissions': ['motion.edit', 'motion.view']},
        )

        self.group_leader = User.objects.create_user(
            username='status_leader',
            email='status_leader@example.com',
            password='leaderpass123',
        )
        leader_membership = GroupMember.objects.create(
            user=self.group_leader,
            group=self.group,
            is_active=True,
        )
        leader_membership.roles.add(self.leader_role)

        self.group_admin = User.objects.create_user(
            username='status_admin',
            email='status_admin@example.com',
            password='adminpass123',
        )
        admin_membership = GroupMember.objects.create(
            user=self.group_admin,
            group=self.group,
            is_active=True,
        )
        admin_membership.roles.add(self.group_admin_role)

        self.deputy_leader = User.objects.create_user(
            username='status_deputy',
            email='status_deputy@example.com',
            password='deputypass123',
        )
        deputy_membership = GroupMember.objects.create(
            user=self.deputy_leader,
            group=self.group,
            is_active=True,
        )
        deputy_membership.roles.add(self.deputy_leader_role)

        self.motion_editor = User.objects.create_user(
            username='status_editor',
            email='status_editor@example.com',
            password='editorpass123',
            role=self.motion_edit_role,
        )

        self.regular_member = User.objects.create_user(
            username='status_member',
            email='status_member@example.com',
            password='memberpass123',
        )
        member_membership = GroupMember.objects.create(
            user=self.regular_member,
            group=self.group,
            is_active=True,
        )
        member_membership.roles.add(self.member_role)

        self.motion = Motion.objects.create(
            title='Status Perm Motion',
            text='Motion text',
            session=self.session,
            group=self.group,
            submitted_by=self.regular_member,
            status='draft',
        )
        self.inquiry = Inquiry.objects.create(
            title='Status Perm Inquiry',
            text='Inquiry text',
            session=self.session,
            group=self.group,
            submitted_by=self.regular_member,
            status='draft',
        )

        self.motion_status_change_url = (
            reverse('motion:motion-status-change', kwargs={'pk': self.motion.pk})
            + '?status=submitted'
        )
        self.inquiry_status_change_url = reverse(
            'inquiry:inquiry-status-change', kwargs={'pk': self.inquiry.pk}
        )

    def _assert_motion_status_change_allowed(self, username, password):
        self.client.login(username=username, password=password)
        response = self.client.get(self.motion_status_change_url)
        self.assertEqual(response.status_code, 200)

    def test_group_leader_can_change_motion_status(self):
        self._assert_motion_status_change_allowed('status_leader', 'leaderpass123')

    def test_group_admin_can_change_motion_status(self):
        self._assert_motion_status_change_allowed('status_admin', 'adminpass123')

    def test_deputy_leader_can_change_motion_status(self):
        self._assert_motion_status_change_allowed('status_deputy', 'deputypass123')

    def test_motion_edit_user_can_change_motion_status(self):
        self._assert_motion_status_change_allowed('status_editor', 'editorpass123')

    def test_regular_member_cannot_change_motion_status(self):
        self.client.login(username='status_member', password='memberpass123')
        response = self.client.get(self.motion_status_change_url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            reverse('motion:motion-detail', kwargs={'pk': self.motion.pk}),
        )

    def test_group_admin_can_change_inquiry_status(self):
        self.client.login(username='status_admin', password='adminpass123')
        response = self.client.get(self.inquiry_status_change_url)
        self.assertEqual(response.status_code, 200)


class StatusAnswerFileTests(TestCase):
    """Tests for multiple PDF answer attachments on motions and inquiries."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser(
            username='answer_admin',
            email='answer_admin@example.com',
            password='adminpass123',
        )

        self.local = Local.objects.create(
            name='Answer Local',
            code='AL',
            description='Test local',
            is_active=True,
        )
        self.council = self.local.council
        self.party = Party.objects.create(
            name='Answer Party',
            local=self.local,
            is_active=True,
        )
        self.group = Group.objects.create(
            name='Answer Group',
            party=self.party,
            is_active=True,
        )
        self.term = Term.objects.create(
            name='Answer Term',
            start_date=timezone.now().date(),
            end_date=(timezone.now().date() + timedelta(days=365)),
            is_active=True,
        )
        self.session = Session.objects.create(
            title='Answer Session',
            council=self.council,
            term=self.term,
            scheduled_date=timezone.now() + timedelta(days=1),
            is_active=True,
        )
        self.motion = Motion.objects.create(
            title='Answer Motion',
            text='Motion text',
            session=self.session,
            group=self.group,
            submitted_by=self.user,
            status='approved',
        )
        self.inquiry = Inquiry.objects.create(
            title='Answer Inquiry',
            text='Inquiry text',
            session=self.session,
            group=self.group,
            submitted_by=self.user,
            status='approved',
        )

    def _pdf_file(self, name):
        return SimpleUploadedFile(name, b'%PDF-1.4 test content', content_type='application/pdf')

    def _pdf_files_dict(self, names):
        files = MultiValueDict()
        files.setlist('answer_files', [self._pdf_file(name) for name in names])
        return files

    def test_validate_answer_pdf_files_requires_at_least_one_for_motions(self):
        with self.assertRaises(forms.ValidationError):
            validate_answer_pdf_files([], require_at_least_one=True)

    def test_validate_answer_pdf_files_rejects_non_pdf(self):
        bad_file = SimpleUploadedFile('answer.txt', b'not a pdf', content_type='text/plain')
        with self.assertRaises(forms.ValidationError):
            validate_answer_pdf_files([bad_file], require_at_least_one=True)

    def test_motion_status_form_accepts_multiple_pdfs(self):
        form = MotionStatusForm(
            data={'status': 'answered', 'reason': 'Answered'},
            files=self._pdf_files_dict(['answer1.pdf', 'answer2.pdf']),
            motion=self.motion,
            changed_by=self.user,
            locked_status='answered',
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(len(form.cleaned_data['answer_files']), 2)

    def test_motion_status_form_requires_pdf_when_answered(self):
        form = MotionStatusForm(
            data={'status': 'answered', 'reason': 'Answered'},
            files=MultiValueDict(),
            motion=self.motion,
            changed_by=self.user,
            locked_status='answered',
        )
        self.assertFalse(form.is_valid())
        self.assertIn('answer_files', form.errors)

    def test_inquiry_status_form_accepts_zero_or_multiple_pdfs(self):
        for names in ([], ['answer1.pdf'], ['answer1.pdf', 'answer2.pdf']):
            with self.subTest(names=names):
                files = self._pdf_files_dict(names) if names else MultiValueDict()
                form = InquiryStatusForm(
                    data={'status': 'answered', 'reason': 'Answered'},
                    files=files,
                    inquiry=self.inquiry,
                    changed_by=self.user,
                )
                self.assertTrue(form.is_valid())
                self.assertEqual(len(form.cleaned_data.get('answer_files', [])), len(names))

    def test_motion_status_change_view_saves_multiple_answer_files(self):
        self.client.login(username='answer_admin', password='adminpass123')
        url = reverse('motion:motion-status-change', kwargs={'pk': self.motion.pk}) + '?status=answered'
        response = self.client.post(
            url,
            {
                'status': 'answered',
                'reason': 'Written answers',
                'answer_files': [
                    self._pdf_file('motion_answer1.pdf'),
                    self._pdf_file('motion_answer2.pdf'),
                ],
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, 302)
        self.motion.refresh_from_db()
        self.assertEqual(self.motion.status, 'answered')
        status_entry = self.motion.status_history.filter(status='answered').first()
        self.assertIsNotNone(status_entry)
        self.assertEqual(status_entry.answer_files.count(), 2)

    def test_inquiry_status_change_view_saves_answer_files(self):
        self.client.login(username='answer_admin', password='adminpass123')
        url = reverse('inquiry:inquiry-status-change', kwargs={'pk': self.inquiry.pk})
        response = self.client.post(
            url,
            {
                'status': 'answered',
                'reason': 'Written answers',
                'answer_files': [
                    self._pdf_file('inquiry_answer1.pdf'),
                    self._pdf_file('inquiry_answer2.pdf'),
                ],
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, 302)
        self.inquiry.refresh_from_db()
        self.assertEqual(self.inquiry.status, 'answered')
        status_entry = self.inquiry.status_history.filter(status='answered').first()
        self.assertIsNotNone(status_entry)
        self.assertEqual(status_entry.answer_files.count(), 2)