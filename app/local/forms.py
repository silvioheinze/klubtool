from django import forms
from .models import Local, Council, Committee, CommitteeMember, Session, Term, Party, TermSeatDistribution, SessionAttachment


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
                # Hide the local field when it's pre-set
                self.fields['local'].widget = forms.HiddenInput()
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
                self.fields['term'].initial = term
                # Hide the term field when it's pre-set
                self.fields['term'].widget = forms.HiddenInput()
            except Term.DoesNotExist:
                pass


class SessionForm(forms.ModelForm):
    """Form for creating and editing Session objects"""
    
    class Meta:
        model = Session
        fields = ['title', 'council', 'term', 'session_type', 'status', 'scheduled_date', 'location', 'agenda', 'minutes', 'notes']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'council': forms.Select(attrs={'class': 'form-select'}),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'session_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'scheduled_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}, format='%Y-%m-%dT%H:%M'),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'agenda': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'minutes': forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter councils to only show active ones
        self.fields['council'].queryset = Council.objects.filter(is_active=True)
        # Filter terms to only show active ones
        self.fields['term'].queryset = Term.objects.filter(is_active=True)
        
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
