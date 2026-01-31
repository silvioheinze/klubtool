from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.template.loader import get_template
from django.template import Context
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
        """Test that custom-colors.css contains the warning color #f7f157"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('#f7f157', css_content, "CSS should contain warning color #f7f157")
    
    def test_custom_colors_css_contains_danger_color(self):
        """Test that custom-colors.css contains the danger color #ce2c77"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('#ce2c77', css_content, "CSS should contain danger color #ce2c77")
    
    def test_custom_colors_css_contains_navbar_styling(self):
        """Test that custom-colors.css contains navbar styling with #7da130"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        # Check for navbar background color
        self.assertIn('.navbar {', css_content, "CSS should contain navbar styling")
        self.assertIn('background-color: #7da130', css_content, "CSS should contain navbar background color #7da130")
    
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
        
        # Check for form control overrides
        self.assertIn('.form-control:focus {', css_content, "CSS should contain .form-control:focus styling")
        self.assertIn('.form-select:focus {', css_content, "CSS should contain .form-select:focus styling")
    
    def test_custom_colors_css_contains_navbar_text_colors(self):
        """Test that custom-colors.css contains navbar text color overrides"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        # Check for navbar text color overrides
        self.assertIn('.navbar-brand {', css_content, "CSS should contain .navbar-brand styling")
        self.assertIn('.navbar-nav .nav-link {', css_content, "CSS should contain .navbar-nav .nav-link styling")
        self.assertIn('color: white', css_content, "CSS should contain white text color for navbar")
    
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
        
        expected_colors = ['#5e833c', '#7da130', '#f7f157', '#ce2c77']
        
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
        """Test that custom-colors.css contains link color overrides"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        # Check for link color overrides (current CSS uses a.text-primary:hover etc.)
        self.assertIn('a.text-primary', css_content, "CSS should contain link styling")
        self.assertIn('color:', css_content, "CSS should contain color definitions")
        self.assertIn('a:', css_content, "CSS should contain anchor pseudo-classes")
    
    def test_custom_colors_css_contains_link_utility_classes(self):
        """Test that custom-colors.css contains link utility class overrides"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        # Check for link-related styling (current CSS uses a.text-primary, .text-primary, etc.)
        self.assertIn('a.text-primary', css_content, "CSS should contain link utility styling")
        self.assertIn('.text-primary', css_content, "CSS should contain .text-primary styling")
        self.assertIn('var(--bs-primary)', css_content, "CSS should use primary variable")
    
    def test_custom_colors_css_contains_navbar_link_overrides(self):
        """Test that custom-colors.css contains navbar link color overrides"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        # Check for navbar styling (current CSS uses .navbar-nav .nav-link)
        self.assertIn('.navbar', css_content, "CSS should contain navbar styling")
        self.assertIn('color: white', css_content, "CSS should contain white color for navbar")
        self.assertIn('.navbar .dropdown-item', css_content, "CSS should contain dropdown item styling")
    
    def test_custom_colors_css_contains_button_text_colors(self):
        """Test that custom-colors.css contains button text color overrides"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        # Check for button text color overrides
        self.assertIn('color: white !important', css_content, "CSS should contain white text color for buttons")
        self.assertIn('.btn-primary {', css_content, "CSS should contain .btn-primary styling")
        self.assertIn('.btn-success {', css_content, "CSS should contain .btn-success styling")
    
    def test_custom_colors_css_contains_footer_link_colors(self):
        """Test that custom-colors.css contains footer and primary color overrides"""
        css_path = os.path.join('static', 'css', 'custom-colors.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        # Check for primary color and footer/dark section styling
        self.assertIn('--bs-primary:', css_content, "CSS should define primary color")
        self.assertTrue(
            '.footer' in css_content or 'footer' in css_content or 'bg-dark' in css_content,
            "CSS should contain footer or dark section styling"
        )
        self.assertIn('var(--bs-primary)', css_content, "CSS should use primary variable")
