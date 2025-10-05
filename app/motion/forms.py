from django import forms
from django.contrib.auth import get_user_model
from django.forms import BaseFormSet, formset_factory
from .models import Motion, MotionVote, MotionComment, MotionAttachment, MotionStatus, MotionGroupDecision
from local.models import Session, Party, Committee
from group.models import Group

User = get_user_model()


class MotionForm(forms.ModelForm):
    """Form for creating and editing Motion objects"""
    
    class Meta:
        model = Motion
        fields = [
            'title', 'text', 'rationale', 'motion_type', 'status',
            'session', 'committee', 'group', 'parties'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'text': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'rationale': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'motion_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.HiddenInput(),
            'session': forms.Select(attrs={'class': 'form-select'}),
            'committee': forms.Select(attrs={'class': 'form-select'}),
            'group': forms.HiddenInput(),
            'parties': forms.SelectMultiple(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter sessions to only show active ones
        self.fields['session'].queryset = Session.objects.filter(is_active=True)
        # Filter parties to only show active ones
        self.fields['parties'].queryset = Party.objects.filter(is_active=True)
        # Filter committees to only show active ones
        self.fields['committee'].queryset = Committee.objects.filter(is_active=True)
        
        # Set status to draft automatically
        self.fields['status'].initial = 'draft'
        
        # Make group field invisible and set default value
        self.fields['group'].widget = forms.HiddenInput()
        self.fields['group'].queryset = Group.objects.filter(is_active=True)
        
        # Set default group if none is provided
        if not self.fields['group'].initial:
            first_group = Group.objects.filter(is_active=True).first()
            if first_group:
                self.fields['group'].initial = first_group.pk
        
        # Set initial session if provided in URL
        session_id = self.initial.get('session') or self.data.get('session')
        if session_id:
            try:
                session = Session.objects.get(pk=session_id)
                self.fields['session'].initial = session.pk
                # Make the session field read-only when it's pre-set
                self.fields['session'].widget.attrs['readonly'] = True
                self.fields['session'].widget.attrs['class'] = 'form-control-plaintext bg-light'
                # Store the session for later use
                self._preset_session = session
                # Override the field validation to always be valid when preset
                self.fields['session'].required = False
            except Session.DoesNotExist:
                pass
    
    def clean(self):
        cleaned_data = super().clean()
        session = cleaned_data.get('session')
        group = cleaned_data.get('group')
        
        # If session is not in cleaned_data but we have a preset session, use it
        if not session and hasattr(self, '_preset_session'):
            session = self._preset_session
            cleaned_data['session'] = session
        
        # If session is still not found, check if it's in the data
        if not session and 'session' in self.data:
            session_id = self.data['session']
            try:
                session = Session.objects.get(pk=session_id)
                cleaned_data['session'] = session
            except (Session.DoesNotExist, ValueError):
                pass
        
        # Ensure group belongs to a party that is in the session's council
        if session and group:
            if group.party.local != session.council.local:
                raise forms.ValidationError(
                    "The selected group must belong to a party in the same local district as the session's council."
                )
        
        return cleaned_data


class MotionFilterForm(forms.Form):
    """Form for filtering motions in the motion list view"""
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by title, text, rationale, or group'
        })
    )
    motion_type = forms.ChoiceField(
        choices=[('', 'All Types')] + Motion.MOTION_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + Motion.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    session = forms.ModelChoiceField(
        queryset=Session.objects.filter(is_active=True),
        required=False,
        empty_label="All Sessions",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    party = forms.ModelChoiceField(
        queryset=Party.objects.filter(is_active=True),
        required=False,
        empty_label="All Parties",
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class MotionVoteForm(forms.ModelForm):
    """Form for recording party votes on motions"""
    
    class Meta:
        model = MotionVote
        fields = ['party', 'approve_votes', 'reject_votes', 'notes']
        widgets = {
            'party': forms.Select(attrs={'class': 'form-select'}),
            'approve_votes': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': '0', 'style': 'width: 80px;'}),
            'reject_votes': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': '0', 'style': 'width: 80px;'}),
            'notes': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Notes...'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.motion = kwargs.pop('motion', None)
        super().__init__(*args, **kwargs)
        
        # Filter parties to only show those in the motion's session council
        if self.motion and self.motion.session and self.motion.session.council:
            self.fields['party'].queryset = Party.objects.filter(
                local=self.motion.session.council.local,
                is_active=True
            )
        
        # Set initial party if provided in URL
        party_id = self.initial.get('party') or self.data.get('party')
        if party_id:
            try:
                party = Party.objects.get(pk=party_id)
                self.fields['party'].initial = party.pk
            except Party.DoesNotExist:
                pass
    
    def clean(self):
        cleaned_data = super().clean()
        approve_votes = cleaned_data.get('approve_votes', 0)
        reject_votes = cleaned_data.get('reject_votes', 0)
        
        # Check if user has already recorded votes for this party on this motion
        if self.motion and cleaned_data.get('party'):
            existing_vote = MotionVote.objects.filter(
                motion=self.motion, 
                party=cleaned_data['party']
            ).first()
            if existing_vote and not self.instance.pk:
                raise forms.ValidationError("Votes for this party on this motion have already been recorded.")
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.motion:
            instance.motion = self.motion
        
        if commit:
            instance.save()
        return instance


class MotionVoteFormSet(BaseFormSet):
    """Formset for recording votes for all parties at once"""
    
    def __init__(self, *args, **kwargs):
        self.motion = kwargs.pop('motion', None)
        super().__init__(*args, **kwargs)
        
        # Set initial data for each party if motion is provided
        if self.motion and self.motion.session and self.motion.session.council:
            parties = Party.objects.filter(
                local=self.motion.session.council.local,
                is_active=True
            )
            
            # Initialize forms with party data
            for i, party in enumerate(parties):
                if i < len(self.forms):
                    self.forms[i].fields['party'].initial = party.pk
                    self.forms[i].fields['party'].widget = forms.HiddenInput()
                    
                    # Set existing vote data if available
                    existing_vote = MotionVote.objects.filter(
                        motion=self.motion,
                        party=party
                    ).first()
                    if existing_vote:
                        self.forms[i].fields['approve_votes'].initial = existing_vote.approve_votes
                        self.forms[i].fields['reject_votes'].initial = existing_vote.reject_votes
                        self.forms[i].fields['abstain_votes'].initial = existing_vote.abstain_votes
                        self.forms[i].fields['notes'].initial = existing_vote.notes
    
    def clean(self):
        """Validate the formset"""
        super().clean()
        
        # Check for duplicate parties
        parties = []
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                party = form.cleaned_data.get('party')
                if party:
                    if party in parties:
                        raise forms.ValidationError(f"Duplicate party: {party.name}")
                    parties.append(party)
        
        return self.cleaned_data


# Create the formset factory
MotionVoteFormSetFactory = formset_factory(
    MotionVoteForm,
    formset=MotionVoteFormSet,
    extra=0,  # No extra forms, only for existing parties
    can_delete=False
)


class MotionCommentForm(forms.ModelForm):
    """Form for adding comments to motions"""
    
    class Meta:
        model = MotionComment
        fields = ['content', 'is_public']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Add your comment here...'
            }),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.motion = kwargs.pop('motion', None)
        self.author = kwargs.pop('author', None)
        super().__init__(*args, **kwargs)
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.motion:
            instance.motion = self.motion
        if self.author:
            instance.author = self.author
        
        if commit:
            instance.save()
        return instance


class MotionAttachmentForm(forms.ModelForm):
    """Form for uploading attachments to motions"""
    
    class Meta:
        model = MotionAttachment
        fields = ['file', 'file_type', 'description']
        widgets = {
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'file_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        self.motion = kwargs.pop('motion', None)
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
        if self.motion:
            instance.motion = self.motion
        if self.uploaded_by:
            instance.uploaded_by = self.uploaded_by
        
        # Set filename
        if instance.file:
            import os
            instance.filename = os.path.basename(instance.file.name)
        
        if commit:
            instance.save()
        return instance


class MotionStatusForm(forms.ModelForm):
    """Form for changing motion status with integrated voting"""
    
    committee = forms.ModelChoiceField(
        queryset=Committee.objects.filter(is_active=True),
        required=False,
        empty_label="Select a committee...",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Select the committee to refer this motion to"
    )
    
    class Meta:
        model = MotionStatus
        fields = ['status', 'committee', 'reason']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'committee': forms.Select(attrs={'class': 'form-select'}),
            'reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Reason for the status change...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.motion = kwargs.pop('motion', None)
        self.changed_by = kwargs.pop('changed_by', None)
        super().__init__(*args, **kwargs)
        
        # Filter committees to only show those from the same council as the motion's session
        if self.motion and self.motion.session and self.motion.session.council:
            self.fields['committee'].queryset = Committee.objects.filter(
                council=self.motion.session.council,
                is_active=True
            )
    
    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        committee = cleaned_data.get('committee')
        
        # If status is 'refer_to_committee', committee is required
        if status == 'refer_to_committee' and not committee:
            raise forms.ValidationError({
                'committee': 'A committee must be selected when referring a motion to committee.'
            })
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.motion:
            instance.motion = self.motion
        if self.changed_by:
            instance.changed_by = self.changed_by
        
        if commit:
            instance.save()
        return instance


class MotionGroupDecisionForm(forms.ModelForm):
    """Form for creating group decisions on motions"""
    
    committee = forms.ModelChoiceField(
        queryset=Committee.objects.filter(is_active=True),
        required=False,
        empty_label="Select a committee...",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Select the committee to refer this motion to"
    )
    
    decision_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
        help_text="Date of the decision"
    )
    
    decision_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}, format='%H:%M'),
        help_text="Time of the decision"
    )
    
    class Meta:
        model = MotionGroupDecision
        fields = ['decision', 'committee', 'description']
        widgets = {
            'decision': forms.Select(attrs={'class': 'form-select'}),
            'committee': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Description of the group decision...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.motion = kwargs.pop('motion', None)
        self.created_by = kwargs.pop('created_by', None)
        super().__init__(*args, **kwargs)
        
        # Filter committees to only show those from the same council as the motion's session
        if self.motion and self.motion.session and self.motion.session.council:
            self.fields['committee'].queryset = Committee.objects.filter(
                council=self.motion.session.council,
                is_active=True
            )
    
    def clean(self):
        cleaned_data = super().clean()
        decision = cleaned_data.get('decision')
        committee = cleaned_data.get('committee')
        
        # If decision is 'refer_to_committee', committee is required
        if decision == 'refer_to_committee' and not committee:
            raise forms.ValidationError({
                'committee': 'A committee must be selected when referring a motion to committee.'
            })
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.motion:
            instance.motion = self.motion
        if self.created_by:
            instance.created_by = self.created_by
        
        # Combine date and time into decision_time
        decision_date = self.cleaned_data.get('decision_date')
        decision_time = self.cleaned_data.get('decision_time')
        if decision_date and decision_time:
            from django.utils import timezone
            import datetime
            instance.decision_time = timezone.make_aware(
                datetime.datetime.combine(decision_date, decision_time)
            )
        
        if commit:
            instance.save()
        return instance
