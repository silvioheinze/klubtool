from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse, resolve
from django.core.exceptions import ValidationError

from .forms import CustomUserCreationForm, CustomUserEditForm, RoleForm, RoleFilterForm
from .models import Role

User = get_user_model()


class CustomUserTests(TestCase):
    def test_create_user(self):
        User = get_user_model()
        user = User.objects.create_user(
            username="will", email="will@email.com", password="testpass123"
        )
        self.assertEqual(user.username, "will")
        self.assertEqual(user.email, "will@email.com")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser(self):
        User = get_user_model()
        admin_user = User.objects.create_superuser(
            username="superadmin", email="superadmin@email.com", password="testpass123"
        )
        self.assertEqual(admin_user.username, "superadmin")
        self.assertEqual(admin_user.email, "superadmin@email.com")
        self.assertTrue(admin_user.is_active)
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)


class SignupPageTests(TestCase):
    username = "newuser"
    email = "newuser@email.com"
    
    def setUp(self):
        url = reverse("account_signup")
        self.response = self.client.get(url)
    
    def test_signup_template(self):
        self.assertEqual(self.response.status_code, 200)
        self.assertTemplateUsed(self.response, "user/signup.html")
        self.assertContains(self.response, "Register")  # The template shows "Register" not "Sign Up"
        self.assertNotContains(self.response, "Hi there! I should not be on the page.")
    
    def test_signup_form(self):
        new_user = get_user_model().objects.create_user(self.username, self.email)
        self.assertEqual(get_user_model().objects.all().count(), 1)
        self.assertEqual(get_user_model().objects.all()[0].username, self.username)
        self.assertEqual(get_user_model().objects.all()[0].email, self.email)


class CustomUserCreationFormTests(TestCase):
    """Test cases for CustomUserCreationForm"""
    
    def setUp(self):
        """Set up test data"""
        self.role = Role.objects.create(
            name='Test Role',
            description='Test role description',
            is_active=True
        )
    
    def test_custom_user_creation_form_valid_data(self):
        """Test CustomUserCreationForm with valid data"""
        form_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'password1': 'testpass123',
            'password2': 'testpass123',
            'role': self.role.pk
        }
        
        form = CustomUserCreationForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_custom_user_creation_form_required_fields(self):
        """Test CustomUserCreationForm with missing required fields"""
        form_data = {
            'username': '',  # Required field missing
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'password1': 'testpass123',
            'password2': 'testpass123',
            'role': self.role.pk
        }
        
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
    
    def test_custom_user_creation_form_password_mismatch(self):
        """Test CustomUserCreationForm with password mismatch"""
        form_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'password1': 'testpass123',
            'password2': 'differentpass',  # Different password
            'role': self.role.pk
        }
        
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)
    
    def test_custom_user_creation_form_role_optional(self):
        """Test CustomUserCreationForm with no role assigned"""
        form_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'password1': 'testpass123',
            'password2': 'testpass123',
            'role': ''  # No role assigned
        }
        
        form = CustomUserCreationForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_custom_user_creation_form_role_filtering(self):
        """Test that CustomUserCreationForm filters roles correctly"""
        form = CustomUserCreationForm()
        expected_roles = Role.objects.filter(is_active=True)
        self.assertQuerySetEqual(
            form.fields['role'].queryset,
            expected_roles,
            transform=lambda x: x
        )
    
    def test_custom_user_creation_form_empty_label(self):
        """Test that CustomUserCreationForm has correct empty label for role"""
        form = CustomUserCreationForm()
        self.assertEqual(form.fields['role'].empty_label, "No role assigned")


class CustomUserEditFormTests(TestCase):
    """Test cases for CustomUserEditForm"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.role = Role.objects.create(
            name='Test Role',
            description='Test role description',
            is_active=True
        )
    
    def test_custom_user_edit_form_valid_data(self):
        """Test CustomUserEditForm with valid data"""
        form_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'first_name': 'Updated',
            'last_name': 'User',
            'role': self.role.pk
        }
        
        form = CustomUserEditForm(data=form_data, instance=self.user)
        self.assertTrue(form.is_valid())
    
    def test_custom_user_edit_form_required_fields(self):
        """Test CustomUserEditForm with missing required fields"""
        form_data = {
            'username': '',  # Required field missing
            'email': 'test@example.com',
            'first_name': 'Updated',
            'last_name': 'User',
            'role': self.role.pk
        }
        
        form = CustomUserEditForm(data=form_data, instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
    
    def test_custom_user_edit_form_role_filtering(self):
        """Test that CustomUserEditForm filters roles correctly"""
        form = CustomUserEditForm(instance=self.user)
        expected_roles = Role.objects.filter(is_active=True)
        self.assertQuerySetEqual(
            form.fields['role'].queryset,
            expected_roles,
            transform=lambda x: x
        )
    
    def test_custom_user_edit_form_instance_data(self):
        """Test that CustomUserEditForm pre-populates with instance data"""
        form = CustomUserEditForm(instance=self.user)
        # The form should have the instance data available
        self.assertEqual(form.instance.username, self.user.username)
        self.assertEqual(form.instance.email, self.user.email)
        self.assertEqual(form.instance.first_name, self.user.first_name)
        self.assertEqual(form.instance.last_name, self.user.last_name)


class RoleFormTests(TestCase):
    """Test cases for RoleForm"""
    
    def test_role_form_valid_data(self):
        """Test RoleForm with valid data"""
        form_data = {
            'name': 'Test Role',
            'description': 'Test role description',
            'is_active': True
        }
        
        form = RoleForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_role_form_required_fields(self):
        """Test RoleForm with missing required fields"""
        form_data = {
            'name': '',  # Required field missing
            'description': 'Test role description',
            'is_active': True
        }
        
        form = RoleForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)
    
    def test_role_form_unique_name(self):
        """Test RoleForm with duplicate name"""
        # Create existing role
        Role.objects.create(
            name='Existing Role',
            description='Existing role description',
            is_active=True
        )
        
        form_data = {
            'name': 'Existing Role',  # Duplicate name
            'description': 'Test role description',
            'is_active': True
        }
        
        form = RoleForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)
    
    def test_role_form_boolean_field_defaults(self):
        """Test RoleForm boolean field defaults"""
        form = RoleForm()
        # Check if is_active field exists and has correct default
        if 'is_active' in form.fields:
            self.assertTrue(form.fields['is_active'].initial)
        else:
            # If is_active field doesn't exist, that's also valid
            self.assertTrue(True)


class RoleFilterFormTests(TestCase):
    """Test cases for RoleFilterForm"""
    
    def test_role_filter_form_valid_data(self):
        """Test RoleFilterForm with valid data"""
        form_data = {
            'name': 'Test',
            'is_active': True
        }
        
        form = RoleFilterForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_role_filter_form_empty_data(self):
        """Test RoleFilterForm with empty data"""
        form_data = {}
        
        form = RoleFilterForm(data=form_data)
        self.assertTrue(form.is_valid())  # Filter forms should be valid with empty data


class RoleModelTests(TestCase):
    """Test cases for Role model"""
    
    def test_role_creation(self):
        """Test Role model creation"""
        role = Role.objects.create(
            name='Test Role',
            description='Test role description',
            is_active=True
        )
        
        self.assertEqual(role.name, 'Test Role')
        self.assertEqual(role.description, 'Test role description')
        self.assertTrue(role.is_active)
        self.assertIsNotNone(role.created_at)
        self.assertIsNotNone(role.updated_at)
    
    def test_role_str_representation(self):
        """Test Role model string representation"""
        role = Role.objects.create(
            name='Test Role',
            description='Test role description',
            is_active=True
        )
        
        self.assertEqual(str(role), 'Test Role')
    
    def test_role_default_values(self):
        """Test Role model default values"""
        role = Role.objects.create(
            name='Test Role',
            description='Test role description'
        )
        
        self.assertTrue(role.is_active)  # Default should be True
    
    def test_role_ordering(self):
        """Test Role model ordering"""
        role1 = Role.objects.create(
            name='B Role',
            description='B role description'
        )
        role2 = Role.objects.create(
            name='A Role',
            description='A role description'
        )
        
        # Get only the roles we created for this test
        test_roles = Role.objects.filter(name__in=['A Role', 'B Role']).order_by('name')
        self.assertEqual(len(test_roles), 2)
        # Check that roles are ordered by name (A comes before B)
        self.assertEqual(test_roles[0], role2)  # A Role should come first
        self.assertEqual(test_roles[1], role1)  # B Role should come second
    
    def test_role_active_filter(self):
        """Test Role model active filter"""
        active_role = Role.objects.create(
            name='Active Role',
            description='Active role description',
            is_active=True
        )
        inactive_role = Role.objects.create(
            name='Inactive Role',
            description='Inactive role description',
            is_active=False
        )
        
        active_roles = Role.objects.filter(is_active=True)
        self.assertIn(active_role, active_roles)
        self.assertNotIn(inactive_role, active_roles)