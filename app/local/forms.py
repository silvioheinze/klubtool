from django import forms
from django.utils import timezone
from .models import Local, Council, Committee, CommitteeMeeting, CommitteeMember, Session, Term, Party, TermSeatDistribution, SessionAttachment


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
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'total_seats': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure date fields are formatted correctly for HTML5 date inputs
        if self.instance and self.instance.pk:
            if self.instance.start_date:
                self.fields['start_date'].widget.attrs['value'] = self.instance.start_date.strftime('%Y-%m-%d')
            if self.instance.end_date:
                self.fields['end_date'].widget.attrs['value'] = self.instance.end_date.strftime('%Y-%m-%d')

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


class PartyForm(forms.ModelForm):
    """Form for creating and editing Party objects"""
    
    class Meta:
        model = Party
        fields = ['name', 'short_name', 'local', 'description', 'color', 'logo']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'short_name': forms.TextInput(attrs={'class': 'form-control'}),
            'local': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter locals to only show active ones
        self.fields['local'].queryset = Local.objects.filter(is_active=True)
        
        # Set initial local if provided in URL
        local_id = self.initial.get('local') or self.data.get('local')
        if local_id:
            try:
                local = Local.objects.get(pk=local_id)
                self.fields['local'].initial = local.pk
                # Don't hide the field - let template handle display
            except Local.DoesNotExist:
                pass


class PartyFilterForm(forms.Form):
    """Form for filtering Party objects"""
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
        # Filter terms to only show active ones
        self.fields['term'].queryset = Term.objects.filter(is_active=True)
        # Filter parties to only show active ones
        self.fields['party'].queryset = Party.objects.filter(is_active=True)
        
        # Set initial term if provided in URL
        term_id = self.initial.get('term') or self.data.get('term')
        if term_id:
            try:
                term = Term.objects.get(pk=term_id)
                self.fields['term'].initial = term.pk
                # Hide the term field when it's pre-set
                self.fields['term'].widget = forms.HiddenInput()
            except Term.DoesNotExist:
                pass


class SessionForm(forms.ModelForm):
    """Form for creating and editing Session objects"""
    
    class Meta:
        model = Session
        fields = ['title', 'council', 'committee', 'term', 'session_type', 'status', 'scheduled_date', 'location', 'agenda', 'minutes', 'notes']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'council': forms.Select(attrs={'class': 'form-select'}),
            'committee': forms.Select(attrs={'class': 'form-select'}),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'session_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'scheduled_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}, format='%Y-%m-%dT%H:%M'),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'agenda': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'minutes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter councils to only show active ones
        self.fields['council'].queryset = Council.objects.filter(is_active=True)
        # Filter committees to only show active ones, initially empty
        self.fields['committee'].queryset = Committee.objects.filter(is_active=True)
        # Filter terms to only show active ones
        self.fields['term'].queryset = Term.objects.filter(is_active=True)
        
        # Set initial council if provided in URL
        council_id = self.initial.get('council') or self.data.get('council')
        if council_id:
            try:
                council = Council.objects.get(pk=council_id)
                self.fields['council'].initial = council
                # Filter committees by council
                self.fields['committee'].queryset = Committee.objects.filter(council=council, is_active=True)
                # Hide the council field when it's pre-set
                self.fields['council'].widget = forms.HiddenInput()
            except Council.DoesNotExist:
                pass
        
        # If instance exists and has a council, filter committees
        if self.instance and self.instance.pk and self.instance.council:
            self.fields['committee'].queryset = Committee.objects.filter(council=self.instance.council, is_active=True)
        
        # Add JavaScript to filter committees when council changes (will be handled in template)

    def clean_scheduled_date(self):
        """Ensure scheduled_date is timezone-aware to avoid DateTimeField warnings."""
        value = self.cleaned_data.get('scheduled_date')
        if value and timezone.is_naive(value):
            return timezone.make_aware(value, timezone.get_current_timezone())
        return value


class SessionFilterForm(forms.Form):
    """Form for filtering sessions in the session list view"""
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by title, location, or notes'
        })
    )
    session_type = forms.ChoiceField(
        choices=[('', 'All Types')] + Session.SESSION_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + Session.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    council = forms.ModelChoiceField(
        queryset=Council.objects.filter(is_active=True),
        required=False,
        empty_label="All Councils",
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class CommitteeForm(forms.ModelForm):
    """Form for creating and editing Committee objects"""
    
    class Meta:
        model = Committee
        fields = ['name', 'abbreviation', 'council', 'term', 'committee_type', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'abbreviation': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '20'}),
            'council': forms.Select(attrs={'class': 'form-select'}),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'committee_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        # On create: auto-select the last (most recent) term before super() so initial is used
        instance = kwargs.get('instance')
        if instance is None or getattr(instance, 'pk', None) is None:
            initial = kwargs.get('initial') or {}
            if 'term' not in initial and not (kwargs.get('data') and 'term' in kwargs.get('data')):
                last_term = Term.objects.filter(is_active=True).order_by('-start_date').first()
                if last_term:
                    initial = dict(initial)
                    initial['term'] = last_term
                    kwargs['initial'] = initial
        super().__init__(*args, **kwargs)
        # Filter councils to only show active ones
        self.fields['council'].queryset = Council.objects.filter(is_active=True)
        # Filter terms to show active ones, ordered by start_date descending (most recent first)
        self.fields['term'].queryset = Term.objects.filter(is_active=True).order_by('-start_date')
        self.fields['term'].required = False
        
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
        fields = ['committee', 'user', 'role', 'joined_date', 'notes']
        widgets = {
            'committee': forms.Select(attrs={'class': 'form-select'}),
            'user': forms.Select(attrs={'class': 'form-select'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'joined_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure joined_date displays and parses as YYYY-MM-DD for HTML5 date input
        self.fields['joined_date'].input_formats = ['%Y-%m-%d']
        # Filter committees to only show active ones
        self.fields['committee'].queryset = Committee.objects.filter(is_active=True)
        
        # Filter users to only show active ones from groups linked to the committee's local
        from django.contrib.auth import get_user_model
        from group.models import GroupMember, Group
        User = get_user_model()
        
        # Get the committee from initial data or form data
        committee_id = self.initial.get('committee') or self.data.get('committee')
        if committee_id:
            try:
                committee = Committee.objects.get(pk=committee_id)
                # Get the local through council
                local = committee.council.local
                # Get all groups for parties in this local
                groups = Group.objects.filter(party__local=local, is_active=True)
                # Get all users who are members of these groups
                user_ids = GroupMember.objects.filter(
                    group__in=groups, 
                    is_active=True
                ).values_list('user_id', flat=True)
                # Filter users to only those in the groups
                self.fields['user'].queryset = User.objects.filter(
                    id__in=user_ids, 
                    is_active=True
                ).order_by('first_name', 'last_name')
                self.fields['committee'].initial = committee
            except Committee.DoesNotExist:
                # Fallback to all active users if committee not found
                self.fields['user'].queryset = User.objects.filter(is_active=True)
        else:
            # If no committee specified, show all active users
            self.fields['user'].queryset = User.objects.filter(is_active=True)


class CommitteeMeetingForm(forms.ModelForm):
    """Form for creating and editing CommitteeMeeting objects. On create, title and is_active are hidden; title is set to committee name + meeting date."""

    class Meta:
        model = CommitteeMeeting
        fields = ['committee', 'title', 'scheduled_date', 'location', 'description', 'is_active']
        widgets = {
            'committee': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'scheduled_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}, format='%Y-%m-%dT%H:%M'),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        committee = kwargs.pop('committee', None)
        super().__init__(*args, **kwargs)
        self.fields['committee'].queryset = Committee.objects.filter(is_active=True)
        if committee:
            self.fields['committee'].queryset = Committee.objects.filter(pk=committee.pk)
            self.fields['committee'].initial = committee
            if not self.instance.pk:
                self.initial['committee'] = committee.pk
        # On create: hide title and is_active; they are set in save()
        if not self.instance.pk:
            del self.fields['title']
            del self.fields['is_active']
        else:
            # On edit: hide labels for title and is_active
            self.fields['title'].label = ''
            self.fields['is_active'].label = ''

    def clean_scheduled_date(self):
        """Ensure scheduled_date is timezone-aware to avoid DateTimeField warnings."""
        value = self.cleaned_data.get('scheduled_date')
        if value and timezone.is_naive(value):
            return timezone.make_aware(value, timezone.get_current_timezone())
        return value

    def save(self, commit=True):
        if not self.instance.pk:
            committee = self.cleaned_data.get('committee')
            scheduled_date = self.cleaned_data.get('scheduled_date')
            if committee and scheduled_date:
                self.instance.title = f"{committee.name} {scheduled_date.strftime('%d.%m.%Y %H:%M')}"
            self.instance.is_active = True
        return super().save(commit=commit)


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


class SessionAttachmentForm(forms.ModelForm):
    """Form for uploading attachments to sessions"""
    
    class Meta:
        model = SessionAttachment
        fields = ['file', 'file_type', 'description']
        widgets = {
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'file_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        self.session = kwargs.pop('session', None)
        self.uploaded_by = kwargs.pop('uploaded_by', None)
        super().__init__(*args, **kwargs)
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Check file size (max 10MB)
            if file.size > 10 * 1024 * 1024:
                raise forms.ValidationError("File size must be under 10MB.")
            
            # Check file extension
            allowed_extensions = ['.pdf', '.doc', '.docx', '.txt', '.jpg', '.jpeg', '.png', '.gif', '.xls', '.xlsx', '.ppt', '.pptx']
            import os
            ext = os.path.splitext(file.name)[1].lower()
            if ext not in allowed_extensions:
                raise forms.ValidationError(f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}")
        
        return file
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.session:
            instance.session = self.session
        if self.uploaded_by:
            instance.uploaded_by = self.uploaded_by
        
        # Set filename
        if instance.file:
            import os
            instance.filename = os.path.basename(instance.file.name)
        
        if commit:
            instance.save()
        return instance
