from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse, resolve
from django.utils import timezone
from datetime import timedelta

from .views import HomePageView
from local.models import Local, Council, Session, Term, Party
from group.models import Group, GroupMember
from motion.models import Motion

User = get_user_model()


class HomepageTests(TestCase):
    """Test cases for the home page"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Create test user
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
            defaults={
                'name': 'Test Council',
                'is_active': True
            }
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
        
        # Create group membership for the user
        self.group_membership = GroupMember.objects.create(
            user=self.user,
            group=self.group,
            is_active=True
        )
    
    def test_url_exists_at_correct_location(self):
        """Test that home URL exists and returns 200"""
        url = reverse("home")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_homepage_template(self):
        """Test that home page uses correct template"""
        url = reverse("home")
        response = self.client.get(url)
        self.assertTemplateUsed(response, "home.html")

    def test_homepage_contains_correct_html(self):
        """Test that home page contains expected content"""
        url = reverse("home")
        response = self.client.get(url)
        self.assertContains(response, 'Welcome to Klubtool')

    def test_homepage_does_not_contain_incorrect_html(self):
        """Test that home page does not contain unexpected content"""
        url = reverse("home")
        response = self.client.get(url)
        self.assertNotContains(response, "Hi there! I should not be on the page.")

    def test_homepage_url_resolves_homepageview(self):
        """Test that home URL resolves to HomePageView"""
        view = resolve("/")
        self.assertEqual(view.func.__name__, HomePageView.as_view().__name__)
    
    def test_homepage_unauthenticated_no_motion_stats(self):
        """Test that unauthenticated users don't see motion statistics"""
        url = reverse("home")
        response = self.client.get(url)
        # Check that statistics section is not rendered
        self.assertNotContains(response, 'motionStatusChart')
        self.assertNotContains(response, 'motionTypeChart')
        self.assertNotContains(response, 'Total Motions')
    
    def test_homepage_authenticated_no_motions_no_stats(self):
        """Test that authenticated users with no motions don't see statistics section"""
        self.client.login(username='testuser', password='testpass123')
        url = reverse("home")
        response = self.client.get(url)
        # Check that statistics section is not rendered (only the comment exists)
        self.assertNotContains(response, 'motionStatusChart')
        self.assertNotContains(response, 'motionTypeChart')
        self.assertNotContains(response, 'Total Motions')
    
    def test_homepage_authenticated_with_motions_shows_stats(self):
        """Test that authenticated users with motions see statistics"""
        # Create motions for the user's group
        Motion.objects.create(
            title='Test Motion 1',
            text='Test motion text',
            session=self.session,
            group=self.group,
            submitted_by=self.user,
            status='draft',
            is_active=True
        )
        Motion.objects.create(
            title='Test Motion 2',
            text='Test motion text',
            session=self.session,
            group=self.group,
            submitted_by=self.user,
            status='approved',
            is_active=True
        )
        
        self.client.login(username='testuser', password='testpass123')
        url = reverse("home")
        response = self.client.get(url)
        
        # Check that statistics section appears
        self.assertContains(response, 'Motion Statistics')
        self.assertContains(response, 'motionStatusChart')
        self.assertContains(response, 'motionTypeChart')
        self.assertContains(response, 'Total Motions')
        self.assertContains(response, 'Recent (30 days)')
    
    def test_homepage_motion_statistics_context(self):
        """Test that motion statistics are included in context"""
        # Create motions with different statuses
        Motion.objects.create(
            title='Draft Motion',
            text='Test',
            session=self.session,
            group=self.group,
            submitted_by=self.user,
            status='draft',
            is_active=True
        )
        Motion.objects.create(
            title='Approved Motion',
            text='Test',
            session=self.session,
            group=self.group,
            submitted_by=self.user,
            status='approved',
            is_active=True
        )
        Motion.objects.create(
            title='Recent Motion',
            text='Test',
            session=self.session,
            group=self.group,
            submitted_by=self.user,
            status='submitted',
            is_active=True,
            submitted_date=timezone.now() - timedelta(days=10)  # Recent motion
        )
        
        self.client.login(username='testuser', password='testpass123')
        url = reverse("home")
        response = self.client.get(url)
        
        # Check context data
        self.assertIn('total_motions', response.context)
        self.assertIn('motion_status_stats', response.context)
        self.assertIn('motion_type_stats', response.context)
        self.assertIn('motion_status_chart_data', response.context)
        self.assertIn('motion_type_chart_data', response.context)
        
        # Verify counts
        self.assertEqual(response.context['total_motions'], 3)
        self.assertEqual(response.context['motion_status_stats'].get('draft', 0), 1)
        self.assertEqual(response.context['motion_status_stats'].get('approved', 0), 1)
        self.assertEqual(response.context['motion_status_stats'].get('submitted', 0), 1)
        # All 3 motions are within 30 days, so recent count should be 3
        self.assertEqual(response.context['recent_motions_count'], 3)
    
    def test_homepage_superuser_sees_all_motions(self):
        """Test that superusers see all motions regardless of group membership"""
        # Create another group and motion
        other_party = Party.objects.create(
            name='Other Party',
            local=self.local,
            is_active=True
        )
        other_group = Group.objects.create(
            name='Other Group',
            party=other_party,
            is_active=True
        )
        
        Motion.objects.create(
            title='Other Group Motion',
            text='Test',
            session=self.session,
            group=other_group,
            submitted_by=self.user,
            status='draft',
            is_active=True
        )
        
        # Make user superuser
        self.user.is_superuser = True
        self.user.save()
        
        self.client.login(username='testuser', password='testpass123')
        url = reverse("home")
        response = self.client.get(url)
        
        # Superuser should see all motions
        self.assertEqual(response.context['total_motions'], 1)
    
    def test_homepage_motion_statistics_filtered_by_group(self):
        """Test that motion statistics are filtered by user's group membership"""
        # Create another group and motion
        other_party = Party.objects.create(
            name='Other Party',
            local=self.local,
            is_active=True
        )
        other_group = Group.objects.create(
            name='Other Group',
            party=other_party,
            is_active=True
        )
        
        # Motion in user's group
        Motion.objects.create(
            title='My Group Motion',
            text='Test',
            session=self.session,
            group=self.group,
            submitted_by=self.user,
            status='draft',
            is_active=True
        )
        
        # Motion in other group (should not be visible)
        Motion.objects.create(
            title='Other Group Motion',
            text='Test',
            session=self.session,
            group=other_group,
            submitted_by=self.user,
            status='draft',
            is_active=True
        )
        
        self.client.login(username='testuser', password='testpass123')
        url = reverse("home")
        response = self.client.get(url)
        
        # Should only see motion from user's group
        self.assertEqual(response.context['total_motions'], 1)