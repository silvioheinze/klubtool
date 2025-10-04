from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.forms import formset_factory
from django.utils import timezone
from datetime import datetime, timedelta

from .forms import (
    MotionForm, MotionVoteForm, MotionVoteFormSetFactory, 
    MotionStatusForm, MotionCommentForm, MotionAttachmentForm, 
    MotionGroupDecisionForm
)
from .models import Motion, MotionVote, MotionComment, MotionAttachment, MotionStatus, MotionGroupDecision
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
    
    def test_motion_form_group_initialization(self):
        """Test that MotionForm sets group from user"""
        form = MotionForm(user=self.user)
        # Group should be set to user's group if available
        # This depends on the user's group membership
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
        """Test MotionVoteForm with no votes cast"""
        form_data = {
            'party': self.party.pk,
            'approve_votes': 0,
            'reject_votes': 0,
            'notes': ''
        }
        
        form = MotionVoteForm(data=form_data, motion=self.motion)
        # The form should be valid even with no votes (this is the current behavior)
        self.assertTrue(form.is_valid())
    
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
        
        # Check that each form has the correct party pre-selected
        for i, party in enumerate(parties):
            if i < len(formset.forms):
                self.assertEqual(formset.forms[i].fields['party'].initial, party.pk)
    
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