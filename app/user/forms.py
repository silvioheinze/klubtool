from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AuthenticationForm
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from .models import Role

CustomUser = get_user_model()


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
    role = forms.ModelChoiceField(
        queryset=Role.objects.filter(is_active=True),
        required=False,
        empty_label="No role assigned"
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'role')


class CustomUserEditForm(UserChangeForm):
    role = forms.ModelChoiceField(
        queryset=Role.objects.filter(is_active=True),
        required=False,
        empty_label="No role assigned"
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'role')


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