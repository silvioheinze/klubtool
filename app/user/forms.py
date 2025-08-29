from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth import get_user_model
from .models import Role

CustomUser = get_user_model()


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
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active')


class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ['name', 'description', 'permissions', 'is_active']
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