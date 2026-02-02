from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AuthenticationForm
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from .models import Role

CustomUser = get_user_model()

try:
    from allauth.account.forms import ChangePasswordForm as AllauthChangePasswordForm
except ImportError:
    AllauthChangePasswordForm = None


if AllauthChangePasswordForm:

    class CustomChangePasswordForm(AllauthChangePasswordForm):
        """Change password form; superusers can change password without entering current password."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if self.user and self.user.is_superuser:
                self.fields["oldpassword"].required = False

        def clean_oldpassword(self):
            if self.user and self.user.is_superuser:
                return self.cleaned_data.get("oldpassword") or ""
            return super().clean_oldpassword()


class CustomAuthenticationForm(AuthenticationForm):
    """Custom authentication form that uses email instead of username"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Change the login field to use email
        self.fields['username'].label = 'Email'
        self.fields['username'].widget.attrs.update({
            'type': 'email',
            'placeholder': 'Enter your email address'
        })
    
    def clean_username(self):
        """Override to handle email-based authentication"""
        username = self.cleaned_data.get('username')
        if username:
            # Try to find user by email
            try:
                user = CustomUser.objects.get(email=username)
                return user.username
            except CustomUser.DoesNotExist:
                # If not found by email, try by username (for backward compatibility)
                try:
                    user = CustomUser.objects.get(username=username)
                    return username
                except CustomUser.DoesNotExist:
                    pass
        return username


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('email', 'first_name', 'last_name')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove username and role fields from the form
        if 'username' in self.fields:
            del self.fields['username']
        if 'role' in self.fields:
            del self.fields['role']
        # Require email for user creation
        self.fields['email'].required = True
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            if CustomUser.objects.filter(email=email).exists():
                raise forms.ValidationError(_('A user with that email already exists.'))
        return email
    
    def clean(self):
        cleaned_data = super().clean()
        first_name = cleaned_data.get('first_name', '').strip()
        last_name = cleaned_data.get('last_name', '').strip()
        email = cleaned_data.get('email', '').strip()
        
        # Generate username based on available data
        if first_name and last_name:
            # Generate username from first_name.last_name
            username = f"{first_name.lower()}.{last_name.lower()}"
        elif first_name:
            # Only first name available
            username = first_name.lower()
        elif last_name:
            # Only last name available
            username = last_name.lower()
        elif email:
            # Use email prefix as fallback
            username = email.split('@')[0].lower()
        else:
            # Fallback to a generic username
            username = 'user'
        
        # Check if username already exists, if so add a number
        original_username = username
        counter = 1
        while CustomUser.objects.filter(username=username).exists():
            username = f"{original_username}{counter}"
            counter += 1
        
        cleaned_data['username'] = username
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        # Set the generated username
        if hasattr(self, 'cleaned_data') and 'username' in self.cleaned_data:
            user.username = self.cleaned_data['username']
        if commit:
            user.save()
        return user


class CustomUserEditForm(UserChangeForm):
    role = forms.ModelChoiceField(
        queryset=Role.objects.filter(is_active=True),
        required=False,
        empty_label="No role assigned"
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'role')

    def __init__(self, *args, allow_set_password=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.allow_set_password = allow_set_password
        # Add Bootstrap classes to visible fields
        for name, field in self.fields.items():
            if hasattr(field.widget, 'attrs'):
                field.widget.attrs.setdefault('class', '')
                if 'form-control' not in field.widget.attrs['class']:
                    field.widget.attrs['class'] = (field.widget.attrs['class'] + ' form-control').strip()
                if field.widget.__class__.__name__ == 'Select':
                    field.widget.attrs['class'] = field.widget.attrs['class'].replace('form-control', 'form-select')
        if allow_set_password:
            self.fields['password1'] = forms.CharField(
                label=_('New password'),
                widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
                required=False,
                help_text=_('Leave blank to keep the current password.'),
            )
            self.fields['password2'] = forms.CharField(
                label=_('New password (again)'),
                widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
                required=False,
            )
            self.fields['password1'].widget.attrs['placeholder'] = _('New password')
            self.fields['password2'].widget.attrs['placeholder'] = _('Confirm new password')

    def clean(self):
        cleaned_data = super().clean()
        if not self.allow_set_password:
            return cleaned_data
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 or password2:
            if password1 != password2:
                self.add_error('password2', _("The two password fields didn't match."))
            elif password1:
                from django.contrib.auth import password_validation
                try:
                    password_validation.validate_password(password1, self.instance)
                except forms.ValidationError as e:
                    self.add_error('password1', e)
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.allow_set_password and self.cleaned_data.get('password1'):
            user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ['name', 'description', 'permissions']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'permissions': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Enter permissions as JSON array, e.g.: ["user.view", "user.edit", "user.delete"]'}),
        }

    def clean_permissions(self):
        permissions = self.cleaned_data.get('permissions')
        if isinstance(permissions, str):
            import json
            try:
                permissions = json.loads(permissions)
            except json.JSONDecodeError:
                raise forms.ValidationError("Invalid JSON format for permissions")
        
        if not isinstance(permissions, dict):
            permissions = {'permissions': permissions if isinstance(permissions, list) else []}
        
        return permissions


class RoleFilterForm(forms.Form):
    """Form for filtering roles in the role list view"""
    name = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Search by name'}))
    is_active = forms.ChoiceField(
        choices=[('', 'All'), ('True', 'Active'), ('False', 'Inactive')],
        required=False,
        initial=''
    )


class LanguageSelectionForm(forms.Form):
    """Form for selecting user language preference"""
    language = forms.ChoiceField(
        choices=[
            ('en', _('English')),
            ('de', _('German')),
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_('Language'),
        help_text=_('Select your preferred language for the interface')
    )


class UserSettingsForm(forms.ModelForm):
    """Form for updating user settings including language and email"""
    language = forms.ChoiceField(
        choices=[
            ('en', _('English')),
            ('de', _('German')),
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_('Language'),
        help_text=_('Select your preferred language for the interface')
    )
    
    class Meta:
        model = CustomUser
        fields = ['email', 'language']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'email': _('Email Address'),
        }
        help_texts = {
            'email': _('Your email address for account notifications and password resets'),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set initial language from user's current language
        if self.instance and self.instance.pk:
            self.fields['language'].initial = getattr(self.instance, 'language', 'de')
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Check if email is already used by another user
            if CustomUser.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError(_('This email address is already in use.'))
        return email


class AdminUserCreationForm(forms.ModelForm):
    """Administrative form for creating users directly (bypassing normal registration)"""
    
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', 'language']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'language': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'username': _('Username'),
            'email': _('Email Address'),
            'first_name': _('First Name'),
            'last_name': _('Last Name'),
            'is_active': _('Active User'),
            'is_staff': _('Staff User'),
            'language': _('Language'),
        }
        help_texts = {
            'username': _('Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'),
            'email': _('Required. Used for account notifications and password resets.'),
            'is_active': _('Designates whether this user should be treated as active. Unselect this instead of deleting accounts.'),
            'is_staff': _('Designates whether the user can log into the admin site.'),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default values for administrative creation
        self.fields['is_active'].initial = True
        self.fields['is_staff'].initial = False
        self.fields['language'].initial = 'de'
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            if CustomUser.objects.filter(username=username).exists():
                raise forms.ValidationError(_('A user with that username already exists.'))
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            if CustomUser.objects.filter(email=email).exists():
                raise forms.ValidationError(_('A user with that email already exists.'))
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        # Set a temporary password that the user will need to change
        user.set_password('temp_password_change_me')
        if commit:
            user.save()
        return user