from django import forms
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .models import Group, GroupMember, GroupMeeting, AgendaItem
from local.models import Party
from user.models import Role

User = get_user_model()

class GroupForm(forms.ModelForm):
    """Form for creating and editing groups"""
    class Meta:
        model = Group
        fields = ['name', 'party', 'calendar_badge_name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'party': forms.Select(attrs={'class': 'form-select'}),
            'calendar_badge_name': forms.TextInput(attrs={'class': 'form-control'}),
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

class GroupInviteForm(forms.Form):
    """Form for inviting a new member by email (sends signup link)"""
    email = forms.EmailField(
        label=_("Email address"),
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': _('Enter email address')}),
        help_text=_("The person will receive an email with a link to create an account.")
    )


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
            'scheduled_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure scheduled_date displays and parses as YYYY-MM-DDTHH:MM for datetime-local input
        self.fields['scheduled_date'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M']
        # On create: hide title (set in save() as "Klubsitzung" + date)
        if not self.instance.pk and 'title' in self.fields:
            del self.fields['title']
        # Set the group field as hidden if provided in initial data
        group_id = self.initial.get('group') or self.data.get('group')
        if group_id:
            self.fields['group'].widget = forms.HiddenInput()
            self.fields['group'].initial = group_id
        else:
            self.fields['group'].widget = forms.Select(attrs={'class': 'form-select'})
        
        # Filter groups to only show active ones
        self.fields['group'].queryset = Group.objects.filter(is_active=True)

    def clean_scheduled_date(self):
        """Ensure scheduled_date is timezone-aware to avoid DateTimeField warnings."""
        value = self.cleaned_data.get('scheduled_date')
        if value and timezone.is_naive(value):
            return timezone.make_aware(value, timezone.get_current_timezone())
        return value

    def save(self, commit=True):
        if not self.instance.pk:
            scheduled_date = self.cleaned_data.get('scheduled_date')
            if scheduled_date:
                self.instance.title = f"Klubsitzung {scheduled_date.strftime('%d.%m.%Y')}"
        return super().save(commit=commit)


class AgendaItemForm(forms.ModelForm):
    """Form for creating and editing agenda items"""
    class Meta:
        model = AgendaItem
        fields = ['title', 'description', 'parent_item', 'order']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'parent_item': forms.Select(attrs={'class': 'form-select'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.meeting = kwargs.pop('meeting', None)
        super().__init__(*args, **kwargs)
        
        if self.meeting:
            # Filter parent items to only show items from the same meeting
            self.fields['parent_item'].queryset = AgendaItem.objects.filter(
                meeting=self.meeting, 
                is_active=True
            ).exclude(pk=self.instance.pk if self.instance.pk else None)
            
            # Set initial order to be the next available order
            if not self.instance.pk:
                max_order = AgendaItem.objects.filter(meeting=self.meeting).aggregate(
                    max_order=models.Max('order')
                )['max_order'] or 0
                self.fields['order'].initial = max_order + 1
        else:
            self.fields['parent_item'].queryset = AgendaItem.objects.none()
    
    def clean(self):
        """Add custom validation and debugging"""
        cleaned_data = super().clean()
        
        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"AgendaItemForm clean - meeting: {self.meeting}")
        logger.debug(f"AgendaItemForm clean - cleaned_data: {cleaned_data}")
        logger.debug(f"AgendaItemForm clean - form data: {self.data}")
        
        return cleaned_data
