from django import forms
from .models import Local, Council, Committee, CommitteeMember, Session, Term, Party, TermSeatDistribution


class LocalForm(forms.ModelForm):
    """Form for creating and editing Local objects"""
    
    class Meta:
        model = Local
        fields = ['name', 'code', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_code(self):
        """Ensure code is uppercase and contains only letters and numbers"""
        code = self.cleaned_data.get('code')
        if code:
            code = code.upper()
            if not code.isalnum():
                raise forms.ValidationError("Code must contain only letters and numbers.")
        return code


class LocalFilterForm(forms.Form):
    """Form for filtering Local objects"""
    name = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Search by name'}))
    code = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Search by code'}))
    is_active = forms.ChoiceField(
        choices=[('', 'All'), ('True', 'Active'), ('False', 'Inactive')],
        required=False,
        initial=''
    )


class CouncilNameForm(forms.ModelForm):
    """Form for editing only the council name"""
    
    class Meta:
        model = Council
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }


class CouncilForm(forms.ModelForm):
    """Form for creating and editing Council objects"""
    
    class Meta:
        model = Council
        fields = ['name', 'local']
        widgets = {
            'local': forms.Select(attrs={'class': 'form-select'}),
        }


class CouncilFilterForm(forms.Form):
    """Form for filtering Council objects"""
    name = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Search by name'}))
    local = forms.ModelChoiceField(
        queryset=Local.objects.filter(is_active=True),
        required=False,
        empty_label="All Locals",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    is_active = forms.ChoiceField(
        choices=[('', 'All'), ('True', 'Active'), ('False', 'Inactive')],
        required=False,
        initial=''
    )


class TermForm(forms.ModelForm):
    """Form for creating and editing Term objects"""
    
    class Meta:
        model = Term
        fields = ['name', 'start_date', 'end_date', 'total_seats', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'total_seats': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date >= end_date:
            raise forms.ValidationError("End date must be after start date.")
        
        return cleaned_data


class TermFilterForm(forms.Form):
    """Form for filtering Term objects"""
    name = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Search by name'}))
    is_active = forms.ChoiceField(
        choices=[('', 'All'), ('True', 'Active'), ('False', 'Inactive')],
        required=False,
        initial=''
    )
    is_current = forms.ChoiceField(
        choices=[('', 'All'), ('True', 'Current'), ('False', 'Not Current')],
        required=False,
        initial=''
    )


class PartyForm(forms.ModelForm):
    """Form for creating and editing Party objects"""
    
    class Meta:
        model = Party
        fields = ['name', 'short_name', 'local', 'description', 'color', 'logo']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'short_name': forms.TextInput(attrs={'class': 'form-control'}),
            'local': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter to only show active locals
        self.fields['local'].queryset = Local.objects.filter(is_active=True)


class PartyFilterForm(forms.Form):
    """Form for filtering Party objects"""
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search parties...'})
    )
    local = forms.ModelChoiceField(
        queryset=Local.objects.filter(is_active=True),
        required=False,
        empty_label="All Locals",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    status = forms.ChoiceField(
        choices=[
            ('', 'All'),
            ('active', 'Active'),
            ('inactive', 'Inactive'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class TermSeatDistributionForm(forms.ModelForm):
    """Form for creating and editing TermSeatDistribution objects"""
    
    class Meta:
        model = TermSeatDistribution
        fields = ['term', 'party', 'seats']
        widgets = {
            'term': forms.Select(attrs={'class': 'form-select'}),
            'party': forms.Select(attrs={'class': 'form-select'}),
            'seats': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter to only show active terms and parties
        self.fields['term'].queryset = Term.objects.filter(is_active=True)
        self.fields['party'].queryset = Party.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        term = cleaned_data.get('term')
        seats = cleaned_data.get('seats')
        
        if term and seats is not None:
            # Check if seats exceed total available seats
            allocated_seats = term.allocated_seats
            if self.instance.pk:
                # For updates, subtract current instance's seats
                allocated_seats -= self.instance.seats
            
            if seats + allocated_seats > term.total_seats:
                raise forms.ValidationError(
                    f"Total allocated seats ({seats + allocated_seats}) cannot exceed "
                    f"total seats in term ({term.total_seats})"
                )
        
        return cleaned_data


class TermSeatDistributionFilterForm(forms.Form):
    """Form for filtering TermSeatDistribution objects"""
    term = forms.ModelChoiceField(
        queryset=Term.objects.filter(is_active=True),
        required=False,
        empty_label="All Terms",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    party = forms.ModelChoiceField(
        queryset=Party.objects.filter(is_active=True),
        required=False,
        empty_label="All Parties",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    min_seats = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Min seats'})
    )
    max_seats = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Max seats'})
    )


class SessionForm(forms.ModelForm):
    """Form for creating and editing Session objects"""
    
    # Separate date and time fields for better user experience
    session_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        help_text="Date of the session"
    )
    session_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        required=False,
        help_text="Time of the session (optional)"
    )
    
    class Meta:
        model = Session
        fields = [
            'title', 'council', 'term', 'session_type', 'status', 
            'start_time', 'end_time', 'location', 
            'agenda', 'minutes', 'notes'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'council': forms.Select(attrs={'class': 'form-select'}),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'session_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'agenda': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'minutes': forms.Textarea(attrs={'rows': 6, 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter councils and terms to only show active ones
        self.fields['council'].queryset = Council.objects.filter(is_active=True)
        self.fields['term'].queryset = Term.objects.filter(is_active=True)
        
        # Set initial values for separate date/time fields if editing
        if self.instance and self.instance.pk and self.instance.scheduled_date:
            self.fields['session_date'].initial = self.instance.scheduled_date.date()
            if self.instance.scheduled_date.time():
                self.fields['session_time'].initial = self.instance.scheduled_date.time()

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError("End time must be after start time.")
        
        return cleaned_data

    def save(self, commit=True):
        """Combine date and time fields into scheduled_date"""
        instance = super().save(commit=False)
        
        session_date = self.cleaned_data.get('session_date')
        session_time = self.cleaned_data.get('session_time')
        
        if session_date:
            from django.utils import timezone
            import datetime
            
            if session_time:
                # Combine date and time
                combined_datetime = datetime.datetime.combine(session_date, session_time)
                instance.scheduled_date = timezone.make_aware(combined_datetime)
            else:
                # Use date with default time (00:00)
                combined_datetime = datetime.datetime.combine(session_date, datetime.time())
                instance.scheduled_date = timezone.make_aware(combined_datetime)
        
        if commit:
            instance.save()
        return instance


class SessionFilterForm(forms.Form):
    """Form for filtering Session objects"""
    title = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Search by title'}))
    council = forms.ModelChoiceField(
        queryset=Council.objects.filter(is_active=True),
        required=False,
        empty_label="All Councils",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    term = forms.ModelChoiceField(
        queryset=Term.objects.filter(is_active=True),
        required=False,
        empty_label="All Terms",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    session_type = forms.ChoiceField(
        choices=[('', 'All Types')] + Session.SESSION_TYPE_CHOICES,
        required=False,
        initial=''
    )
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + Session.STATUS_CHOICES,
        required=False,
        initial=''
    )
    is_active = forms.ChoiceField(
        choices=[('', 'All'), ('True', 'Active'), ('False', 'Inactive')],
        required=False,
        initial=''
    )


class CommitteeForm(forms.ModelForm):
    """Form for creating and editing Committee objects"""
    
    class Meta:
        model = Committee
        fields = ['name', 'council', 'committee_type', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'council': forms.Select(attrs={'class': 'form-select'}),
            'committee_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter councils to only show active ones
        self.fields['council'].queryset = Council.objects.filter(is_active=True)
        
        # Set initial council if provided in URL
        council_id = self.initial.get('council') or self.data.get('council')
        if council_id:
            try:
                council = Council.objects.get(pk=council_id)
                self.fields['council'].initial = council
                # Hide the council field when it's pre-set
                self.fields['council'].widget = forms.HiddenInput()
            except Council.DoesNotExist:
                pass


class CommitteeFilterForm(forms.Form):
    """Form for filtering committees in the committee list view"""
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name, chairperson, or description'
        })
    )
    committee_type = forms.ChoiceField(
        choices=[('', 'All Types')] + Committee.COMMITTEE_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    council = forms.ModelChoiceField(
        queryset=Council.objects.filter(is_active=True),
        required=False,
        empty_label="All Councils",
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class CommitteeMemberForm(forms.ModelForm):
    """Form for creating and editing CommitteeMember objects"""
    
    class Meta:
        model = CommitteeMember
        fields = ['committee', 'user', 'role', 'notes']
        widgets = {
            'committee': forms.Select(attrs={'class': 'form-select'}),
            'user': forms.Select(attrs={'class': 'form-select'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter committees to only show active ones
        self.fields['committee'].queryset = Committee.objects.filter(is_active=True)
        # Filter users to only show active ones
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.fields['user'].queryset = User.objects.filter(is_active=True)
        
        # Set initial committee if provided in URL
        committee_id = self.initial.get('committee') or self.data.get('committee')
        if committee_id:
            try:
                committee = Committee.objects.get(pk=committee_id)
                self.fields['committee'].initial = committee
            except Committee.DoesNotExist:
                pass


class CommitteeMemberFilterForm(forms.Form):
    """Form for filtering committee members in the member list view"""
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by user name or committee name'
        })
    )
    role = forms.ChoiceField(
        choices=[('', 'All Roles')] + CommitteeMember.ROLE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    committee = forms.ModelChoiceField(
        queryset=Committee.objects.filter(is_active=True),
        required=False,
        empty_label="All Committees",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
