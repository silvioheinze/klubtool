from django import forms
from django.contrib.auth import get_user_model
from .models import Group, GroupMember
from local.models import Party

User = get_user_model()

class GroupForm(forms.ModelForm):
    """Form for creating and editing groups"""
    class Meta:
        model = Group
        fields = ['name', 'short_name', 'party', 'description', 'founded_date']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'short_name': forms.TextInput(attrs={'class': 'form-control'}),
            'party': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'founded_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter parties to only show active ones
        self.fields['party'].queryset = self.fields['party'].queryset.filter(is_active=True)

class GroupFilterForm(forms.Form):
    """Form for filtering groups"""
    name = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search by name'}))
    party = forms.ModelChoiceField(queryset=Party.objects.all(), required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    is_active = forms.ChoiceField(choices=[('', 'All'), ('True', 'Active'), ('False', 'Inactive')], required=False, widget=forms.Select(attrs={'class': 'form-select'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter parties to only show active ones
        self.fields['party'].queryset = Party.objects.filter(is_active=True)

class GroupMemberForm(forms.ModelForm):
    """Form for creating and editing group memberships"""
    class Meta:
        model = GroupMember
        fields = ['user', 'group', 'role', 'notes']
        widgets = {
            'user': forms.Select(attrs={'class': 'form-select'}),
            'group': forms.Select(attrs={'class': 'form-select'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter to only show active users and groups
        self.fields['user'].queryset = self.fields['user'].queryset.filter(is_active=True)
        self.fields['group'].queryset = self.fields['group'].queryset.filter(is_active=True)

class GroupMemberFilterForm(forms.Form):
    """Form for filtering group members"""
    user = forms.ModelChoiceField(queryset=User.objects.all(), required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    group = forms.ModelChoiceField(queryset=Group.objects.all(), required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    role = forms.ChoiceField(choices=[('', 'All Roles')] + GroupMember.ROLE_CHOICES, required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    is_active = forms.ChoiceField(choices=[('', 'All'), ('True', 'Active'), ('False', 'Inactive')], required=False, widget=forms.Select(attrs={'class': 'form-select'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter to only show active users and groups
        self.fields['user'].queryset = User.objects.filter(is_active=True)
        self.fields['group'].queryset = Group.objects.filter(is_active=True)
