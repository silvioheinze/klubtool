from django import forms
from django.contrib.auth import get_user_model
from .models import Motion, MotionVote, MotionComment, MotionAttachment
from local.models import Session, Party
from group.models import Group

User = get_user_model()


class MotionForm(forms.ModelForm):
    """Form for creating and editing Motion objects"""
    
    class Meta:
        model = Motion
        fields = [
            'title', 'description', 'motion_type', 'status',
            'session', 'committee', 'group', 'parties'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'motion_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'session': forms.Select(attrs={'class': 'form-select'}),
            'committee': forms.Select(attrs={'class': 'form-select'}),
            'group': forms.Select(attrs={'class': 'form-select'}),
            'parties': forms.SelectMultiple(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter sessions to only show active ones
        self.fields['session'].queryset = Session.objects.filter(is_active=True)
        # Filter groups to only show active ones
        self.fields['group'].queryset = Group.objects.filter(is_active=True)
        # Filter parties to only show active ones
        self.fields['parties'].queryset = Party.objects.filter(is_active=True)
        # Filter committees to only show active ones
        self.fields['committee'].queryset = Committee.objects.filter(is_active=True)
        
        # Set initial session if provided in URL
        session_id = self.initial.get('session') or self.data.get('session')
        if session_id:
            try:
                session = Session.objects.get(pk=session_id)
                self.fields['session'].initial = session
            except Session.DoesNotExist:
                pass
    
    def clean(self):
        cleaned_data = super().clean()
        session = cleaned_data.get('session')
        group = cleaned_data.get('group')
        
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
            'placeholder': 'Search by title, description, or group'
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
    group = forms.ModelChoiceField(
        queryset=Group.objects.filter(is_active=True),
        required=False,
        empty_label="All Groups",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    party = forms.ModelChoiceField(
        queryset=Party.objects.filter(is_active=True),
        required=False,
        empty_label="All Parties",
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class MotionVoteForm(forms.ModelForm):
    """Form for voting on motions"""
    
    class Meta:
        model = MotionVote
        fields = ['vote', 'reason']
        widgets = {
            'vote': forms.Select(attrs={'class': 'form-select'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional reason for your vote'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.motion = kwargs.pop('motion', None)
        self.voter = kwargs.pop('voter', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Check if user has already voted on this motion
        if self.motion and self.voter:
            existing_vote = MotionVote.objects.filter(motion=self.motion, voter=self.voter).first()
            if existing_vote and not self.instance.pk:
                raise forms.ValidationError("You have already voted on this motion.")
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.motion:
            instance.motion = self.motion
        if self.voter:
            instance.voter = self.voter
        
        if commit:
            instance.save()
        return instance


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
