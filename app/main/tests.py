from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import get_template
from django.template import Context
from django.core.mail import get_connection, send_mail
import os
import re

User = get_user_model()


class CustomColorsTests(TestCase):
    """Test cases for custom color functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            language='de'
        )
    
    def test_custom_colors_css_file_exists(self):
        """Test that custom-colors.css file exists"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        self.assertTrue(os.path.exists(css_path), "custom-colors.css file should exist")
    
    def test_custom_colors_css_contains_primary_color(self):
        """Test that custom-colors.css contains the primary color #5e833c"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('#5e833c', css_content, "CSS should contain primary color #5e833c")
    
    def test_custom_colors_css_contains_success_color(self):
        """Test that custom-colors.css contains the success color #7da130"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('#7da130', css_content, "CSS should contain success color #7da130")
    
    def test_custom_colors_css_contains_warning_color(self):
        """Test that custom-colors.css contains the softer warning accent"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('#d4a017', css_content, "CSS should contain warning color #d4a017")
    
    def test_custom_colors_css_contains_danger_color(self):
        """Test that custom-colors.css contains the danger color #ce2c77"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('#ce2c77', css_content, "CSS should contain danger color #ce2c77")
    
    def test_custom_colors_css_contains_navbar_styling(self):
        """Test that custom-colors.css uses light navbar chrome"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('.navbar {', css_content, "CSS should contain navbar styling")
        self.assertIn('var(--kt-surface)', css_content, "Navbar should use light surface token")
        self.assertNotIn('background-color: #7da130', css_content, "Navbar should not use solid green bar")
    
    def test_custom_colors_css_contains_css_variables(self):
        """Test that custom-colors.css contains CSS custom properties"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        # Check for CSS custom properties
        self.assertIn(':root {', css_content, "CSS should contain :root selector for custom properties")
        self.assertIn('--bs-primary:', css_content, "CSS should contain --bs-primary custom property")
        self.assertIn('--bs-success:', css_content, "CSS should contain --bs-success custom property")
        self.assertIn('--bs-warning:', css_content, "CSS should contain --bs-warning custom property")
        self.assertIn('--bs-danger:', css_content, "CSS should contain --bs-danger custom property")
    
    def test_base_template_includes_custom_colors_css(self):
        """Test that _base.html template includes custom-colors.css"""
        template_path = os.path.join('templates', '_base.html')
        with open(template_path, 'r') as f:
            template_content = f.read()
        
        self.assertIn('custom-colors.css', template_content, "_base.html should include custom-colors.css")
    
    def test_base_template_css_loading_order(self):
        """Test that CSS files are loaded in correct order"""
        template_path = os.path.join('templates', '_base.html')
        with open(template_path, 'r') as f:
            template_content = f.read()
        
        # Find the positions of CSS links
        bootstrap_pos = template_content.find('bootstrap.min.css')
        custom_colors_pos = template_content.find('custom-colors.css')
        base_css_pos = template_content.find('base.css')
        
        # Bootstrap should come before custom-colors, custom-colors before base.css
        self.assertLess(bootstrap_pos, custom_colors_pos, "Bootstrap CSS should load before custom-colors.css")
        self.assertLess(custom_colors_pos, base_css_pos, "custom-colors.css should load before base.css")
    
    def test_home_page_loads_with_custom_colors(self):
        """Test that home page loads successfully with custom colors"""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'custom-colors.css')
    
    def test_user_settings_page_loads_with_custom_colors(self):
        """Test that user settings page loads with custom colors"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('user-settings'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'custom-colors.css')
    
    def test_custom_colors_css_contains_button_overrides(self):
        """Test that custom-colors.css contains button color overrides"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        # Check for button color overrides
        self.assertIn('.btn-primary {', css_content, "CSS should contain .btn-primary styling")
        self.assertIn('.btn-success {', css_content, "CSS should contain .btn-success styling")
        self.assertIn('.btn-warning {', css_content, "CSS should contain .btn-warning styling")
        self.assertIn('.btn-danger {', css_content, "CSS should contain .btn-danger styling")
    
    def test_custom_colors_css_contains_alert_overrides(self):
        """Test that custom-colors.css contains alert color overrides"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        # Check for alert color overrides
        self.assertIn('.alert-primary {', css_content, "CSS should contain .alert-primary styling")
        self.assertIn('.alert-success {', css_content, "CSS should contain .alert-success styling")
        self.assertIn('.alert-warning {', css_content, "CSS should contain .alert-warning styling")
        self.assertIn('.alert-danger {', css_content, "CSS should contain .alert-danger styling")
    
    def test_custom_colors_css_contains_text_color_overrides(self):
        """Test that custom-colors.css contains text color overrides"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        # Check for text color overrides
        self.assertIn('.text-primary {', css_content, "CSS should contain .text-primary styling")
        self.assertIn('.text-success {', css_content, "CSS should contain .text-success styling")
        self.assertIn('.text-warning {', css_content, "CSS should contain .text-warning styling")
        self.assertIn('.text-danger {', css_content, "CSS should contain .text-danger styling")
    
    def test_custom_colors_css_contains_background_color_overrides(self):
        """Test that custom-colors.css contains background color overrides"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        # Check for background color overrides
        self.assertIn('.bg-primary {', css_content, "CSS should contain .bg-primary styling")
        self.assertIn('.bg-success {', css_content, "CSS should contain .bg-success styling")
        self.assertIn('.bg-warning {', css_content, "CSS should contain .bg-warning styling")
        self.assertIn('.bg-danger {', css_content, "CSS should contain .bg-danger styling")
    
    def test_custom_colors_css_contains_form_control_overrides(self):
        """Test that custom-colors.css contains form control focus overrides"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        # Check for form control focus overrides (may share a rule block)
        self.assertIn('.form-control:focus', css_content, "CSS should contain .form-control:focus styling")
        self.assertIn('.form-select:focus', css_content, "CSS should contain .form-select:focus styling")
    
    def test_custom_colors_css_contains_navbar_text_colors(self):
        """Test that custom-colors.css contains light navbar text colors"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('.navbar-brand {', css_content, "CSS should contain .navbar-brand styling")
        self.assertIn('.navbar-nav .nav-link {', css_content, "CSS should contain .navbar-nav .nav-link styling")
        self.assertIn('var(--kt-text)', css_content, "CSS should use dark text token for navbar brand")
        self.assertIn('var(--kt-muted)', css_content, "CSS should use muted text token for nav links")
    
    def test_custom_colors_css_contains_dropdown_styling(self):
        """Test that custom-colors.css contains dropdown menu styling"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        # Check for dropdown styling
        self.assertIn('.navbar .dropdown-menu {', css_content, "CSS should contain dropdown menu styling")
        self.assertIn('.navbar .dropdown-item {', css_content, "CSS should contain dropdown item styling")
    
    def test_custom_colors_css_contains_hover_effects(self):
        """Test that custom-colors.css contains hover effects"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        # Check for hover effects
        self.assertIn(':hover', css_content, "CSS should contain hover effects")
        self.assertIn(':focus', css_content, "CSS should contain focus effects")
    
    def test_custom_colors_css_contains_important_declarations(self):
        """Test that custom-colors.css contains !important declarations for proper override"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        # Check for !important declarations
        important_count = css_content.count('!important')
        self.assertGreater(important_count, 0, "CSS should contain !important declarations for proper override")
    
    def test_custom_colors_css_file_size_reasonable(self):
        """Test that custom-colors.css file is not empty and has reasonable size"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        file_size = os.path.getsize(css_path)
        
        # File should exist and have content (more than 100 bytes)
        self.assertGreater(file_size, 100, "custom-colors.css should have substantial content")
        # File should not be too large (less than 50KB)
        self.assertLess(file_size, 50000, "custom-colors.css should not be excessively large")
    
    def test_custom_colors_css_contains_all_expected_colors(self):
        """Test that custom-colors.css contains all expected color values"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        expected_colors = ['#5e833c', '#7da130', '#d4a017', '#ce2c77', '#f4f3ef']
        
        for color in expected_colors:
            with self.subTest(color=color):
                self.assertIn(color, css_content, f"CSS should contain color {color}")
    
    def test_custom_colors_css_contains_rgb_values(self):
        """Test that custom-colors.css contains RGB values for transparency effects"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        # Check for RGBA values (used for transparency effects)
        self.assertIn('rgba(', css_content, "CSS should contain RGBA values for transparency effects")
        # Check for RGB variable definitions
        self.assertIn('-rgb:', css_content, "CSS should contain RGB variable definitions")
    
    def test_custom_colors_css_contains_link_colors(self):
        """Test that custom-colors.css defines Bootstrap link tokens"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('--bs-link-color:', css_content, "CSS should define link color token")
        self.assertIn('--bs-link-hover-color:', css_content, "CSS should define link hover token")
        self.assertIn('.footer a:hover', css_content, "CSS should style footer links")
    
    def test_custom_colors_css_contains_link_utility_classes(self):
        """Test that custom-colors.css contains text utility class overrides"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('.text-primary', css_content, "CSS should contain .text-primary styling")
        self.assertIn('var(--bs-primary)', css_content, "CSS should use primary variable")
    
    def test_custom_colors_css_contains_navbar_link_overrides(self):
        """Test that custom-colors.css contains navbar link color overrides"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('.navbar', css_content, "CSS should contain navbar styling")
        self.assertIn('.navbar-nav .nav-link', css_content, "CSS should style navbar links")
        self.assertIn('.navbar .dropdown-item', css_content, "CSS should contain dropdown item styling")
    
    def test_custom_colors_css_contains_button_text_colors(self):
        """Test that custom-colors.css contains button text color overrides"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        # Check for button text color overrides on filled buttons
        self.assertIn('color: #fff !important', css_content, "CSS should contain light text on primary buttons")
        self.assertIn('.btn-primary {', css_content, "CSS should contain .btn-primary styling")
        self.assertIn('.btn-success {', css_content, "CSS should contain .btn-success styling")
    
    def test_custom_colors_css_contains_footer_link_colors(self):
        """Test that custom-colors.css contains footer and primary color overrides"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        # Check for primary color and light footer styling
        self.assertIn('--bs-primary:', css_content, "CSS should define primary color")
        self.assertIn('.footer', css_content, "CSS should contain footer styling")
        self.assertIn('var(--kt-surface)', css_content, "Footer should use light surface token")
        self.assertIn('var(--bs-primary)', css_content, "CSS should use primary variable")

    def test_card_list_group_items_are_transparent(self):
        """Test that list items inside cards match card body background."""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        self.assertIn('.card .list-group {', css_content)
        self.assertIn('--bs-list-group-bg: transparent', css_content)
        self.assertIn('.card .list-group-item', css_content)
        self.assertIn('background-color: transparent', css_content)

    def test_custom_colors_css_contains_theme_surface_tokens(self):
        """Test that custom-colors.css defines melytics-like surface tokens"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()

        self.assertIn('--kt-canvas', css_content)
        self.assertIn('--kt-surface', css_content)
        self.assertIn('--kt-border', css_content)
        self.assertNotIn('.bg-light {', css_content, "Should not hijack .bg-light with green")

    def test_base_css_uses_inter_font(self):
        """Test that base.css loads Inter instead of Nunito Sans"""
        css_path = os.path.join('static', 'css', 'base.css')
        with open(css_path, 'r') as f:
            css_content = f.read()

        self.assertIn('Inter', css_content, "base.css should import Inter font")
        self.assertNotIn('Nunito Sans', css_content, "base.css should not use Nunito Sans")

    def test_base_template_uses_light_navbar(self):
        """Test that _base.html uses navbar-light without green bg-light"""
        template_path = os.path.join('templates', '_base.html')
        with open(template_path, 'r') as f:
            template_content = f.read()

        self.assertIn('navbar-light', template_content)
        self.assertNotIn('navbar bg-light', template_content)
        self.assertNotIn('footer bg-dark', template_content)
        self.assertIn('class="footer', template_content)


class ThemeLayoutTests(TestCase):
    """Integration tests for melytics-like layout chrome on key pages."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser(
            username='themeuser',
            email='theme@example.com',
            password='testpass123',
            language='de',
        )
        self.client.login(username='themeuser', password='testpass123')

    def _assert_theme_chrome(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'navbar-light')
        self.assertContains(response, 'custom-colors.css')
        self.assertContains(response, 'base.css')
        self.assertNotContains(response, 'navbar bg-light')
        self.assertNotContains(response, 'footer bg-dark')
        self.assertContains(response, 'navbar-toggler')
        self.assertContains(response, 'class="footer')

    def test_home_page_theme_chrome(self):
        self._assert_theme_chrome(self.client.get(reverse('home')))

    def test_settings_page_theme_chrome(self):
        self._assert_theme_chrome(self.client.get(reverse('user-settings')))

    def test_group_detail_and_member_form_theme_chrome(self):
        from district.models import District, Party
        from group.models import Group

        district = District.objects.create(name='Theme District', code='TD')
        party = Party.objects.create(name='Theme Party', district=district)
        group = Group.objects.create(name='Theme Group', party=party)

        detail = self.client.get(reverse('group:group-detail', kwargs={'pk': group.pk}))
        self._assert_theme_chrome(detail)
        self.assertContains(detail, 'card')

        form_url = reverse('group:member-create') + f'?group={group.pk}'
        form_response = self.client.get(form_url)
        self._assert_theme_chrome(form_response)
        self.assertContains(form_response, 'form-control')


class EmailSettingsTests(TestCase):
    """Test cases for email configuration."""

    def test_email_settings_are_configured(self):
        """Verify all required email settings are present and have expected types."""
        self.assertIsNotNone(settings.EMAIL_BACKEND)
        self.assertIsInstance(settings.EMAIL_BACKEND, str)
        self.assertIsInstance(settings.EMAIL_HOST, str)
        self.assertIsInstance(settings.EMAIL_PORT, int)
        self.assertGreaterEqual(settings.EMAIL_PORT, 1)
        self.assertLessEqual(settings.EMAIL_PORT, 65535)
        self.assertIsInstance(settings.EMAIL_USE_TLS, bool)
        self.assertIsInstance(settings.EMAIL_USE_SSL, bool)
        self.assertIsInstance(settings.EMAIL_HOST_USER, str)
        self.assertIsInstance(settings.EMAIL_HOST_PASSWORD, str)
        self.assertIsInstance(settings.EMAIL_TIMEOUT, int)
        self.assertGreaterEqual(settings.EMAIL_TIMEOUT, 0)
        self.assertIsInstance(settings.DEFAULT_FROM_EMAIL, str)
        self.assertIsInstance(settings.SERVER_EMAIL, str)
        self.assertIsInstance(settings.EMAIL_SUBJECT_PREFIX, str)

    def test_email_connection_uses_configured_backend(self):
        """Verify get_connection() returns a connection using EMAIL_BACKEND from settings."""
        connection = get_connection()
        expected_backend = settings.EMAIL_BACKEND
        self.assertEqual(
            connection.__class__.__module__ + '.' + connection.__class__.__name__,
            expected_backend,
            "Connection should use EMAIL_BACKEND from settings"
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='test@example.com',
    )
    def test_send_mail_uses_email_settings(self):
        """Verify send_mail uses DEFAULT_FROM_EMAIL and settings; email is stored in outbox."""
        from django.core import mail as mail_module
        mail_module.outbox = []

        send_mail(
            subject='Test Subject',
            message='Test message',
            from_email=None,  # Will use DEFAULT_FROM_EMAIL
            recipient_list=['recipient@example.com'],
            fail_silently=False,
        )

        self.assertEqual(len(mail_module.outbox), 1)
        self.assertEqual(mail_module.outbox[0].subject, 'Test Subject')
        self.assertEqual(mail_module.outbox[0].from_email, 'test@example.com')
        self.assertEqual(mail_module.outbox[0].to, ['recipient@example.com'])

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
        EMAIL_HOST='smtp.example.com',
        EMAIL_PORT=587,
        EMAIL_USE_TLS=True,
    )
    def test_smtp_settings_produce_valid_connection(self):
        """Verify SMTP backend can be instantiated with configured settings (no actual send)."""
        connection = get_connection()
        self.assertIsNotNone(connection)
        self.assertEqual(connection.host, 'smtp.example.com')
        self.assertEqual(connection.port, 587)
        self.assertTrue(connection.use_tls)
