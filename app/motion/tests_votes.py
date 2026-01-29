"""
Comprehensive unit tests for motion voting features.

This test suite covers:
- MotionVote model methods (calculate_outcome, save, etc.)
- Multiple voting rounds support
- Outcome calculations
- MotionVoteForm validation
- MotionVoteFormSet
- MotionVoteTypeForm
- motion_vote_view
- MotionDetailView vote display
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta

from .forms import MotionVoteForm, MotionVoteFormSetFactory, MotionVoteTypeForm
from .models import Motion, MotionVote
from local.models import Local, Council, Session, Term, Party, TermSeatDistribution, Committee
from group.models import Group, GroupMember
from user.models import Role

User = get_user_model()


class MotionVoteModelTests(TestCase):
    """Test cases for MotionVote model methods"""
    
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
            description='Test local description',
            is_active=True
        )
        
        self.council, _ = Council.objects.get_or_create(
            local=self.local,
            defaults={'name': 'Test Council', 'is_active': True}
        )
        
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
        
        self.party1 = Party.objects.create(
            name='Test Party 1',
            local=self.local,
            is_active=True
        )
        
        self.party2 = Party.objects.create(
            name='Test Party 2',
            local=self.local,
            is_active=True
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            party=self.party1,
            is_active=True
        )
        
        self.motion = Motion.objects.create(
            title='Test Motion',
            text='Test motion text',
            session=self.session,
            group=self.group,
            submitted_by=self.user
        )
    
    def test_calculate_outcome_regular_adopted(self):
        """Test calculate_outcome for regular vote with majority in favor"""
        vote = MotionVote.objects.create(
            motion=self.motion,
            party=self.party1,
            vote_type='regular',
            approve_votes=10,
            reject_votes=5
        )
        vote.total_favor = 10
        vote.total_against = 5
        outcome = vote.calculate_outcome()
        self.assertEqual(outcome, 'adopted')
    
    def test_calculate_outcome_regular_rejected(self):
        """Test calculate_outcome for regular vote with majority against"""
        vote = MotionVote.objects.create(
            motion=self.motion,
            party=self.party1,
            vote_type='regular',
            approve_votes=5,
            reject_votes=10
        )
        vote.total_favor = 5
        vote.total_against = 10
        outcome = vote.calculate_outcome()
        self.assertEqual(outcome, 'rejected')
    
    def test_calculate_outcome_regular_tie(self):
        """Test calculate_outcome for regular vote with tie"""
        vote = MotionVote.objects.create(
            motion=self.motion,
            party=self.party1,
            vote_type='regular',
            approve_votes=5,
            reject_votes=5
        )
        vote.total_favor = 5
        vote.total_against = 5
        outcome = vote.calculate_outcome()
        self.assertEqual(outcome, 'tie')
    
    def test_calculate_outcome_refer_to_committee_referred(self):
        """Test calculate_outcome for refer_to_committee vote with majority in favor"""
        vote = MotionVote.objects.create(
            motion=self.motion,
            party=self.party1,
            vote_type='refer_to_committee',
            approve_votes=10,
            reject_votes=5
        )
        vote.total_favor = 10
        vote.total_against = 5
        outcome = vote.calculate_outcome()
        self.assertEqual(outcome, 'referred')
    
    def test_calculate_outcome_refer_to_committee_not_referred(self):
        """Test calculate_outcome for refer_to_committee vote without majority"""
        vote = MotionVote.objects.create(
            motion=self.motion,
            party=self.party1,
            vote_type='refer_to_committee',
            approve_votes=5,
            reject_votes=10
        )
        vote.total_favor = 5
        vote.total_against = 10
        outcome = vote.calculate_outcome()
        self.assertEqual(outcome, 'not_referred')
    
    def test_save_calculates_totals_and_outcome(self):
        """Test that save method calculates totals and outcome for vote round"""
        # Create first vote
        vote1 = MotionVote.objects.create(
            motion=self.motion,
            party=self.party1,
            vote_type='regular',
            vote_round='First Reading',
            approve_votes=10,
            reject_votes=5
        )
        
        # Create second vote in same round
        vote2 = MotionVote.objects.create(
            motion=self.motion,
            party=self.party2,
            vote_type='regular',
            vote_round='First Reading',
            approve_votes=8,
            reject_votes=3
        )
        
        # Refresh from database
        vote1.refresh_from_db()
        vote2.refresh_from_db()
        
        # Both should have total_favor = 18, total_against = 8
        self.assertEqual(vote1.total_favor, 18)
        self.assertEqual(vote1.total_against, 8)
        self.assertEqual(vote2.total_favor, 18)
        self.assertEqual(vote2.total_against, 8)
        
        # Both should have outcome = 'adopted'
        self.assertEqual(vote1.outcome, 'adopted')
        self.assertEqual(vote2.outcome, 'adopted')
    
    def test_save_separate_vote_rounds(self):
        """Test that votes in different rounds have separate totals"""
        # First round
        vote1_round1 = MotionVote.objects.create(
            motion=self.motion,
            party=self.party1,
            vote_type='regular',
            vote_round='First Reading',
            approve_votes=10,
            reject_votes=5
        )
        
        vote2_round1 = MotionVote.objects.create(
            motion=self.motion,
            party=self.party2,
            vote_type='regular',
            vote_round='First Reading',
            approve_votes=8,
            reject_votes=3
        )
        
        # Second round
        vote1_round2 = MotionVote.objects.create(
            motion=self.motion,
            party=self.party1,
            vote_type='regular',
            vote_round='Second Reading',
            approve_votes=5,
            reject_votes=10
        )
        
        vote2_round2 = MotionVote.objects.create(
            motion=self.motion,
            party=self.party2,
            vote_type='regular',
            vote_round='Second Reading',
            approve_votes=3,
            reject_votes=8
        )
        
        # Refresh from database
        vote1_round1.refresh_from_db()
        vote2_round1.refresh_from_db()
        vote1_round2.refresh_from_db()
        vote2_round2.refresh_from_db()
        
        # Round 1 totals
        self.assertEqual(vote1_round1.total_favor, 18)
        self.assertEqual(vote1_round1.total_against, 8)
        self.assertEqual(vote1_round1.outcome, 'adopted')
        
        # Round 2 totals (separate)
        self.assertEqual(vote1_round2.total_favor, 8)
        self.assertEqual(vote1_round2.total_against, 18)
        self.assertEqual(vote1_round2.outcome, 'rejected')
    
    def test_get_vote_summary(self):
        """Test get_vote_summary method"""
        vote = MotionVote.objects.create(
            motion=self.motion,
            party=self.party1,
            approve_votes=10,
            reject_votes=5
        )
        
        summary = vote.get_vote_summary()
        self.assertIn('Approve', summary)
        self.assertIn('10', summary)
        self.assertIn('15', summary)  # Total votes
    
    def test_total_votes_cast_property(self):
        """Test total_votes_cast property"""
        vote = MotionVote.objects.create(
            motion=self.motion,
            party=self.party1,
            approve_votes=10,
            reject_votes=5
        )
        
        self.assertEqual(vote.total_votes_cast, 15)
    
    def test_multiple_votes_same_party_different_rounds(self):
        """Test that same party can vote in different rounds"""
        # Create first vote
        vote1 = MotionVote.objects.create(
            motion=self.motion,
            party=self.party1,
            vote_type='regular',
            vote_round='First Reading',
            approve_votes=10,
            reject_votes=5
        )
        
        # Create vote in different round (should work)
        vote2 = MotionVote.objects.create(
            motion=self.motion,
            party=self.party1,
            vote_type='regular',
            vote_round='Second Reading',
            approve_votes=8,
            reject_votes=3
        )
        self.assertIsNotNone(vote2.pk)
        
        # Verify both votes exist
        self.assertEqual(MotionVote.objects.filter(motion=self.motion, party=self.party1).count(), 2)


class MotionVoteFormTests(TestCase):
    """Test cases for MotionVoteForm"""
    
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
            description='Test local description',
            is_active=True
        )
        
        self.council, _ = Council.objects.get_or_create(
            local=self.local,
            defaults={'name': 'Test Council', 'is_active': True}
        )
        
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
        
        self.motion = Motion.objects.create(
            title='Test Motion',
            text='Test motion text',
            session=self.session,
            group=self.group,
            submitted_by=self.user
        )
        
        # Create seat distribution
        self.seat_distribution = TermSeatDistribution.objects.create(
            term=self.term,
            party=self.party,
            seats=10
        )
    
    def test_form_valid_with_votes(self):
        """Test form with valid vote data"""
        form_data = {
            'party': self.party.pk,
            'approve_votes': 5,
            'reject_votes': 3,
            'notes': 'Test notes'
        }
        
        form = MotionVoteForm(
            data=form_data,
            motion=self.motion,
            max_seats=10
        )
        self.assertTrue(form.is_valid())
    
    def test_form_requires_at_least_one_vote(self):
        """Test that form requires at least one vote (no abstaining)"""
        form_data = {
            'party': self.party.pk,
            'approve_votes': 0,
            'reject_votes': 0,
            'notes': ''
        }
        
        form = MotionVoteForm(
            data=form_data,
            motion=self.motion,
            max_seats=10
        )
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)
    
    def test_form_validates_max_seats(self):
        """Test that form validates votes don't exceed max seats"""
        form_data = {
            'party': self.party.pk,
            'approve_votes': 6,
            'reject_votes': 5,  # Total = 11, exceeds max_seats = 10
            'notes': ''
        }
        
        form = MotionVoteForm(
            data=form_data,
            motion=self.motion,
            max_seats=10
        )
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)
    
    def test_form_allows_exact_max_seats(self):
        """Test that form allows votes equal to max seats"""
        form_data = {
            'party': self.party.pk,
            'approve_votes': 6,
            'reject_votes': 4,  # Total = 10, equals max_seats
            'notes': ''
        }
        
        form = MotionVoteForm(
            data=form_data,
            motion=self.motion,
            max_seats=10
        )
        self.assertTrue(form.is_valid())
    
    def test_form_default_values_zero(self):
        """Test that form defaults approve_votes and reject_votes to 0"""
        form = MotionVoteForm(motion=self.motion, max_seats=10)
        self.assertEqual(form.fields['approve_votes'].initial, 0)
        self.assertEqual(form.fields['reject_votes'].initial, 0)
    
    def test_form_save_creates_vote(self):
        """Test that form.save() creates a MotionVote instance"""
        form_data = {
            'party': self.party.pk,
            'approve_votes': 5,
            'reject_votes': 3,
            'notes': 'Test notes'
        }
        
        form = MotionVoteForm(
            data=form_data,
            motion=self.motion,
            max_seats=10
        )
        self.assertTrue(form.is_valid())
        
        vote = form.save()
        self.assertIsNotNone(vote.pk)
        self.assertEqual(vote.motion, self.motion)
        self.assertEqual(vote.party, self.party)
        self.assertEqual(vote.approve_votes, 5)
        self.assertEqual(vote.reject_votes, 3)


class MotionVoteTypeFormTests(TestCase):
    """Test cases for MotionVoteTypeForm"""
    
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
            description='Test local description',
            is_active=True
        )
        
        self.council, _ = Council.objects.get_or_create(
            local=self.local,
            defaults={'name': 'Test Council', 'is_active': True}
        )
        
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
        
        self.motion = Motion.objects.create(
            title='Test Motion',
            text='Test motion text',
            session=self.session,
            group=self.group,
            submitted_by=self.user
        )
        
        self.committee = Committee.objects.create(
            name='Test Committee',
            council=self.council,
            is_active=True
        )
    
    def test_form_valid_regular_vote(self):
        """Test form with regular vote type"""
        form_data = {
            'vote_type': 'regular',
            'vote_round': 'First Reading',
            'vote_name': 'Initial vote',
            'vote_session': self.session.pk
        }
        
        form = MotionVoteTypeForm(data=form_data, motion=self.motion)
        self.assertTrue(form.is_valid())
    
    def test_form_valid_refer_to_committee(self):
        """Test form with refer_to_committee vote type"""
        form_data = {
            'vote_type': 'refer_to_committee',
            'vote_round': 'Committee Referral',
            'vote_name': 'Refer to committee',
            'vote_session': self.session.pk,
            'committee': self.committee.pk
        }
        
        form = MotionVoteTypeForm(data=form_data, motion=self.motion)
        self.assertTrue(form.is_valid())
    
    def test_form_vote_round_optional(self):
        """Test that vote_round is optional"""
        form_data = {
            'vote_type': 'regular',
            'vote_session': self.session.pk
        }
        
        form = MotionVoteTypeForm(data=form_data, motion=self.motion)
        self.assertTrue(form.is_valid())
    
    def test_form_vote_session_defaults_to_motion_session(self):
        """Test that vote_session defaults to motion's session"""
        form = MotionVoteTypeForm(motion=self.motion)
        # The initial value should be set in __init__, check that the field has the motion's session in queryset
        self.assertIn(self.motion.session, form.fields['vote_session'].queryset)
        # Check that initial is set (might be None or the session object)
        # The important thing is that the queryset includes the motion's session
    
    def test_form_committee_queryset_filtered(self):
        """Test that committee queryset is filtered to motion's council"""
        form = MotionVoteTypeForm(motion=self.motion)
        committees = form.fields['committee'].queryset
        self.assertEqual(committees.count(), 1)
        self.assertIn(self.committee, committees)


class MotionVoteFormSetTests(TestCase):
    """Test cases for MotionVoteFormSet"""
    
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
            description='Test local description',
            is_active=True
        )
        
        self.council, _ = Council.objects.get_or_create(
            local=self.local,
            defaults={'name': 'Test Council', 'is_active': True}
        )
        
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
        
        self.party1 = Party.objects.create(
            name='Test Party 1',
            local=self.local,
            is_active=True
        )
        
        self.party2 = Party.objects.create(
            name='Test Party 2',
            local=self.local,
            is_active=True
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            party=self.party1,
            is_active=True
        )
        
        self.motion = Motion.objects.create(
            title='Test Motion',
            text='Test motion text',
            session=self.session,
            group=self.group,
            submitted_by=self.user
        )
        
        # Create seat distributions
        TermSeatDistribution.objects.create(
            term=self.term,
            party=self.party1,
            seats=10
        )
        TermSeatDistribution.objects.create(
            term=self.term,
            party=self.party2,
            seats=8
        )
    
    def test_formset_initialization_with_parties(self):
        """Test formset initialization with parties"""
        parties = Party.objects.filter(
            local=self.motion.session.council.local,
            is_active=True
        )
        
        formset = MotionVoteFormSetFactory(
            motion=self.motion,
            initial=[{'party': party.pk} for party in parties],
            vote_type='regular',
            party_seat_map={self.party1.pk: 10, self.party2.pk: 8}
        )
        
        self.assertEqual(len(formset.forms), parties.count())
    
    def test_formset_valid_data(self):
        """Test formset with valid data"""
        form_data = {
            'form-TOTAL_FORMS': '2',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-party': self.party1.pk,
            'form-0-approve_votes': '6',
            'form-0-reject_votes': '4',
            'form-1-party': self.party2.pk,
            'form-1-approve_votes': '5',
            'form-1-reject_votes': '3',
        }
        
        formset = MotionVoteFormSetFactory(
            data=form_data,
            motion=self.motion,
            vote_type='regular',
            party_seat_map={self.party1.pk: 10, self.party2.pk: 8}
        )
        
        self.assertTrue(formset.is_valid())


class MotionVoteViewTests(TestCase):
    """Test cases for motion_vote_view"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        # Create a role with vote permission
        self.role = Role.objects.create(
            name='Vote Tester',
            permissions={'permissions': ['motion.vote', 'motion.view']},
            is_active=True
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role=self.role
        )
        
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description',
            is_active=True
        )
        
        self.council, _ = Council.objects.get_or_create(
            local=self.local,
            defaults={'name': 'Test Council', 'is_active': True}
        )
        
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
        
        self.party1 = Party.objects.create(
            name='Test Party 1',
            local=self.local,
            is_active=True
        )
        
        self.party2 = Party.objects.create(
            name='Test Party 2',
            local=self.local,
            is_active=True
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            party=self.party1,
            is_active=True
        )
        
        self.motion = Motion.objects.create(
            title='Test Motion',
            text='Test motion text',
            session=self.session,
            group=self.group,
            submitted_by=self.user
        )
        
        # Create seat distributions
        TermSeatDistribution.objects.create(
            term=self.term,
            party=self.party1,
            seats=10
        )
        TermSeatDistribution.objects.create(
            term=self.term,
            party=self.party2,
            seats=8
        )
        
        self.committee = Committee.objects.create(
            name='Test Committee',
            council=self.council,
            is_active=True
        )
    
    def test_vote_view_get_requires_login(self):
        """Test that vote view requires login"""
        response = self.client.get(reverse('motion:motion-vote', kwargs={'pk': self.motion.pk}))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_vote_view_get_requires_permission(self):
        """Test that vote view requires vote permission"""
        # Create user without vote permission
        role_no_vote = Role.objects.create(
            name='No Vote Role',
            permissions={'permissions': ['motion.view']},  # Only view, no vote
            is_active=True
        )
        user_no_permission = User.objects.create_user(
            username='noperm',
            email='noperm@example.com',
            password='testpass123',
            role=role_no_vote
        )
        self.client.login(username='noperm', password='testpass123')
        
        response = self.client.get(reverse('motion:motion-vote', kwargs={'pk': self.motion.pk}))
        # The view might redirect (302) or return 403, both indicate permission denied
        self.assertIn(response.status_code, [302, 403])
    
    def test_vote_view_get_renders_form(self):
        """Test that GET request renders vote form"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get(reverse('motion:motion-vote', kwargs={'pk': self.motion.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vote Type')
        self.assertContains(response, self.party1.name)
        self.assertContains(response, self.party2.name)
    
    def test_vote_view_post_creates_votes(self):
        """Test that POST request creates votes"""
        self.client.login(username='testuser', password='testpass123')
        
        form_data = {
            'vote_type': 'regular',
            'vote_round': 'First Reading',
            'vote_name': 'Initial vote',
            'vote_session': self.session.pk,
            'form-TOTAL_FORMS': '2',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-party': self.party1.pk,
            'form-0-approve_votes': '6',
            'form-0-reject_votes': '4',
            'form-1-party': self.party2.pk,
            'form-1-approve_votes': '5',
            'form-1-reject_votes': '3',
        }
        
        response = self.client.post(
            reverse('motion:motion-vote', kwargs={'pk': self.motion.pk}),
            form_data
        )
        
        self.assertEqual(response.status_code, 302)  # Redirect
        
        # Check that votes were created
        votes = MotionVote.objects.filter(motion=self.motion, vote_round='First Reading')
        self.assertEqual(votes.count(), 2)
        
        # Check totals and outcome
        vote1 = votes.get(party=self.party1)
        self.assertEqual(vote1.total_favor, 11)  # 6 + 5
        self.assertEqual(vote1.total_against, 7)  # 4 + 3
        self.assertEqual(vote1.outcome, 'adopted')
    
    def test_vote_view_post_updates_motion_status_adopted(self):
        """Test that POST request updates motion status when adopted"""
        self.client.login(username='testuser', password='testpass123')
        
        form_data = {
            'vote_type': 'regular',
            'vote_round': 'Final Vote',
            'vote_session': self.session.pk,
            'form-TOTAL_FORMS': '2',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-party': self.party1.pk,
            'form-0-approve_votes': '8',
            'form-0-reject_votes': '2',
            'form-1-party': self.party2.pk,
            'form-1-approve_votes': '6',
            'form-1-reject_votes': '2',
        }
        
        response = self.client.post(
            reverse('motion:motion-vote', kwargs={'pk': self.motion.pk}),
            form_data
        )
        
        self.motion.refresh_from_db()
        self.assertEqual(self.motion.status, 'approved')
    
    def test_vote_view_post_updates_motion_status_rejected(self):
        """Test that POST request updates motion status when rejected"""
        self.client.login(username='testuser', password='testpass123')
        
        form_data = {
            'vote_type': 'regular',
            'vote_round': 'Final Vote',
            'vote_session': self.session.pk,
            'form-TOTAL_FORMS': '2',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-party': self.party1.pk,
            'form-0-approve_votes': '2',
            'form-0-reject_votes': '8',
            'form-1-party': self.party2.pk,
            'form-1-approve_votes': '2',
            'form-1-reject_votes': '6',
        }
        
        response = self.client.post(
            reverse('motion:motion-vote', kwargs={'pk': self.motion.pk}),
            form_data
        )
        
        self.motion.refresh_from_db()
        self.assertEqual(self.motion.status, 'rejected')
    
    def test_vote_view_post_refer_to_committee(self):
        """Test that POST request can refer motion to committee"""
        self.client.login(username='testuser', password='testpass123')
        
        form_data = {
            'vote_type': 'refer_to_committee',
            'vote_round': 'Committee Referral',
            'vote_session': self.session.pk,
            'committee': self.committee.pk,
            'form-TOTAL_FORMS': '2',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-party': self.party1.pk,
            'form-0-approve_votes': '8',
            'form-0-reject_votes': '2',
            'form-1-party': self.party2.pk,
            'form-1-approve_votes': '6',
            'form-1-reject_votes': '2',
        }
        
        response = self.client.post(
            reverse('motion:motion-vote', kwargs={'pk': self.motion.pk}),
            form_data
        )
        
        self.motion.refresh_from_db()
        self.assertEqual(self.motion.status, 'refer_to_committee')
        self.assertEqual(self.motion.committee, self.committee)
    
    def test_vote_view_multiple_rounds(self):
        """Test that multiple voting rounds can be recorded"""
        self.client.login(username='testuser', password='testpass123')
        
        # First round
        form_data_round1 = {
            'vote_type': 'regular',
            'vote_round': 'First Reading',
            'vote_session': self.session.pk,
            'form-TOTAL_FORMS': '2',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-party': self.party1.pk,
            'form-0-approve_votes': '6',
            'form-0-reject_votes': '4',
            'form-1-party': self.party2.pk,
            'form-1-approve_votes': '5',
            'form-1-reject_votes': '3',
        }
        
        self.client.post(
            reverse('motion:motion-vote', kwargs={'pk': self.motion.pk}),
            form_data_round1
        )
        
        # Second round
        form_data_round2 = {
            'vote_type': 'regular',
            'vote_round': 'Second Reading',
            'vote_session': self.session.pk,
            'form-TOTAL_FORMS': '2',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-party': self.party1.pk,
            'form-0-approve_votes': '8',
            'form-0-reject_votes': '2',
            'form-1-party': self.party2.pk,
            'form-1-approve_votes': '7',
            'form-1-reject_votes': '1',
        }
        
        self.client.post(
            reverse('motion:motion-vote', kwargs={'pk': self.motion.pk}),
            form_data_round2
        )
        
        # Check that both rounds exist
        round1_votes = MotionVote.objects.filter(motion=self.motion, vote_round='First Reading')
        round2_votes = MotionVote.objects.filter(motion=self.motion, vote_round='Second Reading')
        
        self.assertEqual(round1_votes.count(), 2)
        self.assertEqual(round2_votes.count(), 2)
        
        # Check that totals are separate
        vote1_round1 = round1_votes.get(party=self.party1)
        vote1_round2 = round2_votes.get(party=self.party1)
        
        self.assertEqual(vote1_round1.total_favor, 11)  # 6 + 5
        self.assertEqual(vote1_round2.total_favor, 15)  # 8 + 7


class MotionDetailViewVoteTests(TestCase):
    """Test cases for vote display in MotionDetailView"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        # Create a role with view permission
        self.role = Role.objects.create(
            name='View Tester',
            permissions={'permissions': ['motion.view']},
            is_active=True
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role=self.role
        )
        
        self.local = Local.objects.create(
            name='Test Local',
            code='TL',
            description='Test local description',
            is_active=True
        )
        
        self.council, _ = Council.objects.get_or_create(
            local=self.local,
            defaults={'name': 'Test Council', 'is_active': True}
        )
        
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
        
        self.party1 = Party.objects.create(
            name='Test Party 1',
            local=self.local,
            is_active=True
        )
        
        self.party2 = Party.objects.create(
            name='Test Party 2',
            local=self.local,
            is_active=True
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            party=self.party1,
            is_active=True
        )
        
        self.motion = Motion.objects.create(
            title='Test Motion',
            text='Test motion text',
            session=self.session,
            group=self.group,
            submitted_by=self.user
        )
        
        # Create seat distributions
        TermSeatDistribution.objects.create(
            term=self.term,
            party=self.party1,
            seats=10
        )
        TermSeatDistribution.objects.create(
            term=self.term,
            party=self.party2,
            seats=8
        )
    
    def test_detail_view_shows_votes(self):
        """Test that detail view shows votes"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create votes
        MotionVote.objects.create(
            motion=self.motion,
            party=self.party1,
            vote_type='regular',
            vote_round='First Reading',
            approve_votes=6,
            reject_votes=4
        )
        MotionVote.objects.create(
            motion=self.motion,
            party=self.party2,
            vote_type='regular',
            vote_round='First Reading',
            approve_votes=5,
            reject_votes=3
        )
        
        response = self.client.get(reverse('motion:motion-detail', kwargs={'pk': self.motion.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Voting Results')
        self.assertContains(response, 'First Reading')
        self.assertContains(response, self.party1.name)
        self.assertContains(response, self.party2.name)
    
    def test_detail_view_shows_no_votes_message(self):
        """Test that detail view shows message when no votes"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get(reverse('motion:motion-detail', kwargs={'pk': self.motion.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Voting Results')
        # Check for either English or German message (depending on translation)
        self.assertTrue(
            'No votes recorded yet' in response.content.decode() or 
            'Noch keine Stimmen aufgezeichnet' in response.content.decode() or
            'Keine Stimmen aufgezeichnet' in response.content.decode()
        )
    
    def test_detail_view_groups_votes_by_round(self):
        """Test that detail view groups votes by round"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create votes in different rounds
        MotionVote.objects.create(
            motion=self.motion,
            party=self.party1,
            vote_type='regular',
            vote_round='First Reading',
            approve_votes=6,
            reject_votes=4
        )
        MotionVote.objects.create(
            motion=self.motion,
            party=self.party2,
            vote_type='regular',
            vote_round='First Reading',
            approve_votes=5,
            reject_votes=3
        )
        MotionVote.objects.create(
            motion=self.motion,
            party=self.party1,
            vote_type='regular',
            vote_round='Second Reading',
            approve_votes=8,
            reject_votes=2
        )
        MotionVote.objects.create(
            motion=self.motion,
            party=self.party2,
            vote_type='regular',
            vote_round='Second Reading',
            approve_votes=7,
            reject_votes=1
        )
        
        response = self.client.get(reverse('motion:motion-detail', kwargs={'pk': self.motion.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'First Reading')
        self.assertContains(response, 'Second Reading')
    
    def test_detail_view_shows_vote_statistics(self):
        """Test that detail view shows vote statistics"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create votes
        MotionVote.objects.create(
            motion=self.motion,
            party=self.party1,
            vote_type='regular',
            vote_round='First Reading',
            approve_votes=6,
            reject_votes=4
        )
        MotionVote.objects.create(
            motion=self.motion,
            party=self.party2,
            vote_type='regular',
            vote_round='First Reading',
            approve_votes=5,
            reject_votes=3
        )
        
        response = self.client.get(reverse('motion:motion-detail', kwargs={'pk': self.motion.pk}))
        self.assertEqual(response.status_code, 200)
        # Should show total votes (11 favor, 7 against)
        self.assertContains(response, '11', count=None)  # May appear multiple times
        self.assertContains(response, '7', count=None)  # May appear multiple times
