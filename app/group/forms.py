from django import forms
from django.contrib.auth import get_user_model
from .models import Group, GroupMember, GroupMeeting
from local.models import Party
from user.models import Role

User = get_user_model()

class GroupForm(forms.ModelForm):
    """Form for creating and editing groups"""
    class Meta:
        model = Group
        fields = ['name', 'party']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'party': forms.Select(attrs={'class': 'form-select'}),
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
        fields = ['user', 'group', 'roles', 'notes']
        widgets = {
            'user': forms.Select(attrs={'class': 'form-select'}),
            'group': forms.Select(attrs={'class': 'form-select'}),
            'roles': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter to only show active users and groups
        self.fields['user'].queryset = self.fields['user'].queryset.filter(is_active=True)
        self.fields['group'].queryset = self.fields['group'].queryset.filter(is_active=True)
        # Filter to only show active roles
        self.fields['roles'].queryset = Role.objects.filter(is_active=True)

class GroupMemberFilterForm(forms.Form):
    """Form for filtering group members"""
    user = forms.ModelChoiceField(queryset=User.objects.all(), required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    group = forms.ModelChoiceField(queryset=Group.objects.all(), required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    role = forms.ModelChoiceField(queryset=Role.objects.all(), required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    is_active = forms.ChoiceField(choices=[('', 'All'), ('True', 'Active'), ('False', 'Inactive')], required=False, widget=forms.Select(attrs={'class': 'form-select'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter to only show active users and groups
        self.fields['user'].queryset = User.objects.filter(is_active=True)
        self.fields['group'].queryset = Group.objects.filter(is_active=True)
        # Filter to only show active roles
        self.fields['role'].queryset = Role.objects.filter(is_active=True)


class GroupMeetingForm(forms.ModelForm):
    """Form for creating and editing group meetings"""
    class Meta:
        model = GroupMeeting
        fields = ['title', 'scheduled_date', 'location', 'description', 'group']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'scheduled_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set the group field as hidden if provided in initial data
        group_id = self.initial.get('group') or self.data.get('group')
        if group_id:
            self.fields['group'].widget = forms.HiddenInput()
            self.fields['group'].initial = group_id
        else:
            self.fields['group'].widget = forms.Select(attrs={'class': 'form-select'})
        
        # Filter groups to only show active ones
        self.fields['group'].queryset = Group.objects.filter(is_active=True)
    
