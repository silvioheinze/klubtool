from django import forms
from django.contrib.auth import get_user_model
from django.forms import BaseFormSet, formset_factory
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from .models import Motion, MotionVote, MotionComment, MotionAttachment, MotionStatus, MotionGroupDecision, Question, QuestionStatus, QuestionAttachment, Tag
from local.models import Session, Party, Committee
from group.models import Group, GroupMember

User = get_user_model()


class TagsField(forms.CharField):
    """Custom field for tags that accepts comma-separated text and creates new tags"""
    
    def __init__(self, *args, **kwargs):
        # Remove ManyToManyField-specific kwargs that CharField doesn't accept
        kwargs.pop('queryset', None)
        kwargs.pop('limit_choices_to', None)
        kwargs.pop('to_field_name', None)
        
        kwargs.setdefault('widget', forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter tags separated by commas (e.g., environment, budget, housing)'
        }))
        kwargs.setdefault('required', False)
        super().__init__(*args, **kwargs)
    
    def to_python(self, value):
        """Convert comma-separated string to list of tag names"""
        if not value:
            return []
        # Split by comma, strip whitespace, and filter out empty strings
        tag_names = [name.strip() for name in str(value).split(',') if name.strip()]
        return tag_names
    
    def prepare_value(self, value):
        """Convert list of tag objects to comma-separated string for display"""
        if not value:
            return ''
        if isinstance(value, str):
            return value
        # If it's a queryset or list of Tag objects, get their names
        if hasattr(value, 'all'):
            # It's a queryset
            return ', '.join([tag.name for tag in value.all()])
        elif isinstance(value, list):
            # It's a list - could be Tag objects or strings
            if value and hasattr(value[0], 'name'):
                return ', '.join([tag.name for tag in value])
            else:
                return ', '.join(value)
        return ''
    
    def clean(self, value):
        """Validate and return list of tag names"""
        # First convert to list of tag names
        tag_names = self.to_python(value)
        if not tag_names:
            return []
        # Validate tag names (no special characters except spaces, hyphens, underscores)
        import re
        for tag_name in tag_names:
            if not re.match(r'^[a-zA-Z0-9\s\-_äöüÄÖÜß]+$', tag_name):
                raise forms.ValidationError(
                    f'Tag "{tag_name}" contains invalid characters. Tags can only contain letters, numbers, spaces, hyphens, and underscores.'
                )
            if len(tag_name) > 50:
                raise forms.ValidationError(
                    f'Tag "{tag_name}" is too long. Maximum length is 50 characters.'
                )
        return tag_names


class MotionForm(forms.ModelForm):
    """Form for creating and editing Motion objects"""
    
    class Meta:
        model = Motion
        fields = [
            'title', 'text', 'rationale', 'motion_type', 'status',
            'session', 'committee', 'group', 'parties', 'interventions', 'tags'
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
            'interventions': forms.SelectMultiple(attrs={'class': 'form-select'}),
        }
        field_classes = {
            'tags': TagsField,
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
        # Replace tags field with custom TagsField
        self.fields['tags'] = TagsField()
        
        # Set initial value if editing existing motion
        if self.instance and self.instance.pk:
            self.fields['tags'].initial = ', '.join([tag.name for tag in self.instance.tags.all()])
        
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
        
        # Filter interventions to only show users from the motion's group
        if self.instance and self.instance.pk and self.instance.group:
            # Editing existing motion - filter by the motion's group
            group = self.instance.group
            group_member_users = User.objects.filter(
                group_memberships__group=group,
                group_memberships__is_active=True
            ).distinct()
            self.fields['interventions'].queryset = group_member_users
        elif 'group' in self.initial or 'group' in self.data:
            # Creating new motion with group set
            group_id = self.initial.get('group') or self.data.get('group')
            if group_id:
                try:
                    group = Group.objects.get(pk=group_id)
                    group_member_users = User.objects.filter(
                        group_memberships__group=group,
                        group_memberships__is_active=True
                    ).distinct()
                    self.fields['interventions'].queryset = group_member_users
                except Group.DoesNotExist:
                    self.fields['interventions'].queryset = User.objects.none()
            else:
                self.fields['interventions'].queryset = User.objects.none()
        else:
            # No group set yet - show no users
            self.fields['interventions'].queryset = User.objects.none()
    
    def clean_tags(self):
        """Handle tag creation and return tag objects"""
        tag_names = self.cleaned_data.get('tags', [])
        if not tag_names:
            return []
        
        tag_objects = []
        for tag_name in tag_names:
            # Try to get existing tag by name (case-insensitive)
            tag = Tag.objects.filter(name__iexact=tag_name, is_active=True).first()
            if not tag:
                # Create new tag
                tag = Tag.objects.create(
                    name=tag_name,
                    slug=slugify(tag_name),
                    is_active=True
                )
            tag_objects.append(tag)
        
        return tag_objects
    
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
        
        # Validate that interventions are from the motion's group
        interventions = cleaned_data.get('interventions', [])
        if group and interventions:
            group_member_users = User.objects.filter(
                group_memberships__group=group,
                group_memberships__is_active=True
            ).distinct()
            invalid_users = [user for user in interventions if user not in group_member_users]
            if invalid_users:
                raise forms.ValidationError(
                    f"All interventions must be members of the motion's group. Invalid users: {', '.join([u.username for u in invalid_users])}"
                )
        
        return cleaned_data
    
    def save(self, commit=True):
        """Override save to handle tags after instance is saved"""
        instance = super().save(commit=False)
        if commit:
            instance.save()
            # Save many-to-many relationships
            self.save_m2m()
        
        # Handle tags separately since they need to be created/retrieved
        if 'tags' in self.cleaned_data:
            tag_objects = self.cleaned_data['tags']
            if commit:
                instance.tags.set(tag_objects)
            else:
                # Store for later
                instance._tags_to_set = tag_objects
        
        return instance


class QuestionForm(forms.ModelForm):
    """Form for creating and editing Question objects"""
    
    class Meta:
        model = Question
        fields = [
            'title', 'text', 'answer', 'status',
            'session', 'group', 'parties', 'interventions', 'tags'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'text': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'answer': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'status': forms.HiddenInput(),
            'session': forms.Select(attrs={'class': 'form-select'}),
            'group': forms.HiddenInput(),
            'parties': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'interventions': forms.SelectMultiple(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter sessions to only show active ones
        self.fields['session'].queryset = Session.objects.filter(is_active=True)
        # Filter parties to only show active ones
        self.fields['parties'].queryset = Party.objects.filter(is_active=True)
        # Replace tags field with custom TagsField
        self.fields['tags'] = TagsField()
        
        # Set initial value if editing existing question
        if self.instance and self.instance.pk:
            self.fields['tags'].initial = ', '.join([tag.name for tag in self.instance.tags.all()])
        
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
        
        # Filter interventions to only show users from the question's group
        if self.instance and self.instance.pk and self.instance.group:
            # Editing existing question - filter by the question's group
            group = self.instance.group
            group_member_users = User.objects.filter(
                group_memberships__group=group,
                group_memberships__is_active=True
            ).distinct()
            self.fields['interventions'].queryset = group_member_users
        elif 'group' in self.initial or 'group' in self.data:
            # Creating new question with group set
            group_id = self.initial.get('group') or self.data.get('group')
            if group_id:
                try:
                    group = Group.objects.get(pk=group_id)
                    group_member_users = User.objects.filter(
                        group_memberships__group=group,
                        group_memberships__is_active=True
                    ).distinct()
                    self.fields['interventions'].queryset = group_member_users
                except Group.DoesNotExist:
                    self.fields['interventions'].queryset = User.objects.none()
            else:
                self.fields['interventions'].queryset = User.objects.none()
        else:
            # No group set yet - show no users
            self.fields['interventions'].queryset = User.objects.none()
    
    def clean_tags(self):
        """Handle tag creation and return tag objects"""
        tag_names = self.cleaned_data.get('tags', [])
        if not tag_names:
            return []
        
        tag_objects = []
        for tag_name in tag_names:
            # Try to get existing tag by name (case-insensitive)
            tag = Tag.objects.filter(name__iexact=tag_name, is_active=True).first()
            if not tag:
                # Create new tag
                tag = Tag.objects.create(
                    name=tag_name,
                    slug=slugify(tag_name),
                    is_active=True
                )
            tag_objects.append(tag)
        
        return tag_objects
    
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
        
        # Validate that interventions are from the question's group
        interventions = cleaned_data.get('interventions', [])
        if group and interventions:
            group_member_users = User.objects.filter(
                group_memberships__group=group,
                group_memberships__is_active=True
            ).distinct()
            invalid_users = [user for user in interventions if user not in group_member_users]
            if invalid_users:
                raise forms.ValidationError(
                    f"All interventions must be members of the question's group. Invalid users: {', '.join([u.username for u in invalid_users])}"
                )
        
        return cleaned_data
    
    def save(self, commit=True):
        """Override save to handle tags after instance is saved"""
        instance = super().save(commit=False)
        if commit:
            instance.save()
            # Save many-to-many relationships
            self.save_m2m()
        
        # Handle tags separately since they need to be created/retrieved
        if 'tags' in self.cleaned_data:
            tag_objects = self.cleaned_data['tags']
            if commit:
                instance.tags.set(tag_objects)
            else:
                # Store for later
                instance._tags_to_set = tag_objects
        
        return instance


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
    
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.filter(is_active=True),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
        label=_('Tags')
    )


class QuestionFilterForm(forms.Form):
    """Form for filtering questions in the question list view"""
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by title, text, or group'
        })
    )
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + Question.STATUS_CHOICES,
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
    
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.filter(is_active=True),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
        label=_('Tags')
    )


class MotionVoteForm(forms.ModelForm):
    """Form for recording party votes on motions"""
    
    class Meta:
        model = MotionVote
        fields = ['party', 'approve_votes', 'reject_votes', 'notes']
        widgets = {
            'party': forms.HiddenInput(),  # Party will be set automatically
            'approve_votes': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'type': 'number', 'min': '0', 'step': '1', 'style': 'width: 80px;'}),
            'reject_votes': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'type': 'number', 'min': '0', 'step': '1', 'style': 'width: 80px;'}),
            'notes': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Notes...'}),
        }
    
    def __init__(self, *args, **kwargs):
        # Pop custom kwargs before calling super
        self.motion = kwargs.pop('motion', None)
        self.max_seats = kwargs.pop('max_seats', None)
        
        # Get initial data if provided
        initial = kwargs.get('initial', {})
        party_id = initial.get('party') if initial else None
        
        # If we have initial party data and no instance, create instance with party set
        # We must set the actual Party object (not just party_id) so that when
        # ModelForm builds field values it doesn't trigger RelatedObjectDoesNotExist
        if party_id and 'instance' not in kwargs:
            from motion.models import MotionVote
            from local.models import Party
            instance = MotionVote()
            instance.party_id = party_id
            if self.motion:
                instance.motion_id = self.motion.pk if hasattr(self.motion, 'pk') else None
            # Set the actual Party object so instance.party is available (avoids RelatedObjectDoesNotExist)
            try:
                instance.party = Party.objects.get(pk=party_id)
            except Party.DoesNotExist:
                pass
            kwargs['instance'] = instance
        
        super().__init__(*args, **kwargs)
        
        # Make vote fields not required
        self.fields['approve_votes'].required = False
        self.fields['reject_votes'].required = False
        # Make party not required - it will only be validated if votes are entered
        self.fields['party'].required = False
        
        # Ensure instance has party_id and party object set from initial data if available
        # ModelForm and templates access instance.party, so we need the actual object
        if self.initial and self.initial.get('party') and self.instance:
            try:
                from local.models import Party
                party_id = int(self.initial['party'])
                if not hasattr(self.instance, 'party_id') or self.instance.party_id != party_id:
                    self.instance.party_id = party_id
                # Ensure instance.party is set so no RelatedObjectDoesNotExist when rendering
                if not getattr(self.instance, 'party', None) or self.instance.party_id != party_id:
                    self.instance.party = Party.objects.get(pk=party_id)
            except (ValueError, TypeError, Party.DoesNotExist):
                pass
        
        # Ensure instance has motion_id set if motion is provided
        if self.motion and self.instance:
            motion_id = self.motion.pk if hasattr(self.motion, 'pk') else None
            if motion_id and (not hasattr(self.instance, 'motion_id') or self.instance.motion_id != motion_id):
                self.instance.motion_id = motion_id
        
        # Set default values to 0 if not already set
        # Don't set value attribute - let the browser handle it naturally
        if not self.initial.get('approve_votes') and not self.data:
            self.fields['approve_votes'].initial = 0
        if not self.initial.get('reject_votes') and not self.data:
            self.fields['reject_votes'].initial = 0
        
        # Set max value for vote inputs based on party's max seats
        if self.max_seats is not None:
            self.fields['approve_votes'].widget.attrs['max'] = str(self.max_seats)
            self.fields['reject_votes'].widget.attrs['max'] = str(self.max_seats)
            # Store max_value for template access
            self.fields['approve_votes'].max_value = self.max_seats
            self.fields['reject_votes'].max_value = self.max_seats
    
    def clean(self):
        import logging
        logger = logging.getLogger(__name__)
        
        cleaned_data = super().clean()
        approve_votes = cleaned_data.get('approve_votes', 0) or 0
        reject_votes = cleaned_data.get('reject_votes', 0) or 0
        total_votes = approve_votes + reject_votes
        party = cleaned_data.get('party')
        
        # If party is missing from POST (e.g. hidden input not submitted) but we have
        # initial/instance data, use it so validation doesn't fail incorrectly
        if not party and (self.initial.get('party') or getattr(self.instance, 'party_id', None)):
            from local.models import Party
            try:
                party_id = self.initial.get('party') or self.instance.party_id
                if party_id:
                    party = Party.objects.get(pk=party_id)
                    cleaned_data['party'] = party
            except (Party.DoesNotExist, ValueError, TypeError):
                pass
        
        party = cleaned_data.get('party')
        logger.debug(f"MotionVoteForm.clean() - approve_votes={approve_votes}, reject_votes={reject_votes}, total={total_votes}, max_seats={self.max_seats}, party={party}")
        
        # Require at least one vote when party is selected (no abstaining)
        if party and total_votes == 0:
            logger.debug("Validation error: party selected but no votes (abstaining not allowed)")
            raise forms.ValidationError({
                '__all__': _('At least one vote (in favor or against) must be cast. Abstaining is not allowed.')
            })
        
        # Only validate further if votes have been entered (non-zero)
        if total_votes > 0:
            # If votes are entered, party is required
            if not party:
                logger.debug(f"Validation error: votes entered but no party selected")
                raise forms.ValidationError({
                    'party': _('A party must be selected when votes are entered.')
                })
            
            # Validate that total votes don't exceed max seats
            if self.max_seats is not None and total_votes > self.max_seats:
                logger.debug(f"Validation error: total votes {total_votes} exceeds max_seats {self.max_seats}")
                raise forms.ValidationError(
                    _('Total votes (%(total)d) cannot exceed party\'s maximum seats (%(max)d) for this term.') % {
                        'total': total_votes,
                        'max': self.max_seats
                    }
                )
        # Empty forms (no party) are allowed in the formset; formset will ensure at least one form has votes
        
        logger.debug(f"MotionVoteForm.clean() - validation passed")
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
        self.vote_type = kwargs.pop('vote_type', 'regular')
        self.party_seat_map = kwargs.pop('party_seat_map', {})
        initial = kwargs.pop('initial', [])
        
        # Remove any other unexpected kwargs that BaseFormSet doesn't accept
        # BaseFormSet accepts: data, files, auto_id, prefix, initial, error_class, form_kwargs, error_messages
        valid_kwargs = {}
        valid_keys = ['data', 'files', 'auto_id', 'prefix', 'error_class', 'form_kwargs', 'error_messages']
        for key in valid_keys:
            if key in kwargs:
                valid_kwargs[key] = kwargs.pop(key)
        
        # Set up form_kwargs to pass motion to each form
        if 'form_kwargs' not in valid_kwargs:
            valid_kwargs['form_kwargs'] = {}
        valid_kwargs['form_kwargs']['motion'] = self.motion
        
        # If we have initial data but no POST data, we need to set up the management form
        if not args and initial and 'data' not in valid_kwargs:
            # Create management form data to tell Django how many forms to create
            management_data = {
                'form-TOTAL_FORMS': str(len(initial)),
                'form-INITIAL_FORMS': str(len(initial)),
                'form-MIN_NUM_FORMS': '0',
                'form-MAX_NUM_FORMS': '1000',
            }
            valid_kwargs['data'] = management_data
        
        super().__init__(*args, initial=initial, **valid_kwargs)
        
        # Set max_seats for each form based on party
        for i, form in enumerate(self.forms):
            # Get party ID from initial data or form data
            party_id = None
            if form.initial and form.initial.get('party'):
                party_id = form.initial.get('party')
            elif form.data:
                # Try to get from form data
                prefix = form.prefix
                party_id = form.data.get(f'{prefix}-party')
                if party_id:
                    try:
                        party_id = int(party_id)
                    except (ValueError, TypeError):
                        party_id = None
            
            if party_id:
                max_seats = self.party_seat_map.get(party_id, 0)
                form.max_seats = max_seats
                # Update widget max attributes (convert to string for HTML)
                form.fields['approve_votes'].widget.attrs['max'] = str(max_seats)
                form.fields['reject_votes'].widget.attrs['max'] = str(max_seats)
    
    def clean(self):
        """Validate the formset"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.debug(f"MotionVoteFormSet.clean() - processing {len(self.forms)} forms")
        
        # Call super().clean() which validates all forms
        # Forms without votes should pass validation since party is now optional
        super().clean()
        
        # After super().clean(), forms with errors won't have cleaned_data
        # We need to handle this gracefully
        
        # Check if this formset actually has POST data with vote fields
        # If the formset was created with minimal POST data (only management form fields),
        # we should skip vote requirement validation
        has_vote_post_data = False
        if self.data:
            # Check if there are any vote-related fields in POST data (not just management form)
            for key in self.data.keys():
                if ('approve_votes' in key or 'reject_votes' in key) and not key.startswith('form-TOTAL') and not key.startswith('form-INITIAL') and not key.startswith('form-MIN') and not key.startswith('form-MAX'):
                    has_vote_post_data = True
                    break
        
        # If no vote POST data exists, this formset is optional (status doesn't require votes)
        if not has_vote_post_data:
            logger.debug("MotionVoteFormSet.clean() - no vote POST data, skipping vote requirement")
            return
        
        # Check for duplicate parties and count total votes
        # Count votes from raw POST data to ensure we catch all votes, even if forms have validation errors
        parties = []
        total_votes_cast = 0
        
        # First, count votes from raw POST data (this catches votes even if forms have errors)
        if self.data:
            for i, form in enumerate(self.forms):
                prefix = form.prefix
                approve_str = self.data.get(f'{prefix}-approve_votes', '')
                reject_str = self.data.get(f'{prefix}-reject_votes', '')
                try:
                    approve_votes = int(approve_str) if approve_str and approve_str.strip() else 0
                    reject_votes = int(reject_str) if reject_str and reject_str.strip() else 0
                    total_votes_cast += approve_votes + reject_votes
                    if approve_votes > 0 or reject_votes > 0:
                        logger.debug(f"Form {i} (from raw POST data): approve={approve_votes}, reject={reject_votes}")
                except (ValueError, TypeError):
                    pass
        
        # Also check cleaned_data for duplicate party validation
        # Only check forms that have votes (to avoid errors on empty forms)
        for i, form in enumerate(self.forms):
            logger.debug(f"Form {i}: has cleaned_data={form.cleaned_data is not None}, is_valid={form.is_valid()}, errors={form.errors}")
            
            # Check for duplicate parties using cleaned_data (if available)
            # Only validate forms that have votes entered
            if form.cleaned_data is not None and not form.cleaned_data.get('DELETE', False):
                party = form.cleaned_data.get('party')
                approve_votes = form.cleaned_data.get('approve_votes', 0) or 0
                reject_votes = form.cleaned_data.get('reject_votes', 0) or 0
                
                # Only check for duplicates if this form has votes
                if (approve_votes > 0 or reject_votes > 0) and party:
                    if party in parties:
                        logger.debug(f"Duplicate party found: {party.name}")
                        raise forms.ValidationError(f"Duplicate party: {party.name}")
                    parties.append(party)
        
        logger.debug(f"Total votes cast across all forms: {total_votes_cast}")
        
        # Require that at least one vote is cast (only if we have POST data with vote fields)
        if total_votes_cast == 0:
            logger.debug("Validation error: no votes cast but vote POST data exists")
            raise forms.ValidationError(_('At least one vote (in favor or against) must be cast across all parties. Abstaining is not allowed.'))
        
        logger.debug(f"MotionVoteFormSet.clean() - validation passed")
        

class MotionVoteTypeForm(forms.Form):
    """Form for selecting vote type, round, session, and committee (if applicable)"""
    
    vote_type = forms.ChoiceField(
        choices=MotionVote.VOTE_TYPE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label=_('Vote Type'),
        initial='regular'
    )
    
    vote_name = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Custom name/description for this voting round')}),
        label=_('Vote Name'),
        help_text=_('Optional description for this voting round')
    )
    
    vote_session = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label=_("Use motion's session"),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_('Session'),
        help_text=_('Session where this vote was cast (defaults to motion\'s session)')
    )
    
    committee = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label=_("Select Committee"),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_('Committee (if referring to committee)')
    )
    
    def __init__(self, *args, **kwargs):
        self.motion = kwargs.pop('motion', None)
        super().__init__(*args, **kwargs)
        
        # Filter committees based on motion's council
        if self.motion and self.motion.session and self.motion.session.council:
            self.fields['committee'].queryset = Committee.objects.filter(
                council=self.motion.session.council,
                is_active=True
            )
            # Filter sessions for the same council
            self.fields['vote_session'].queryset = Session.objects.filter(
                council=self.motion.session.council,
                is_active=True
            ).order_by('-scheduled_date')
        else:
            self.fields['committee'].queryset = Committee.objects.none()
            self.fields['vote_session'].queryset = Session.objects.none()
        
        # Set default session to motion's session
        if self.motion and self.motion.session:
            self.fields['vote_session'].initial = self.motion.session
    
    def clean(self):
        cleaned_data = super().clean()
        vote_type = cleaned_data.get('vote_type')
        committee = cleaned_data.get('committee')
        
        # If vote type is 'refer_to_committee', committee is required
        if vote_type == 'refer_to_committee' and not committee:
            raise forms.ValidationError({
                'committee': _('Committee is required when vote type is "Refer to Committee".')
            })
        
        return cleaned_data


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


class QuestionAttachmentForm(forms.ModelForm):
    """Form for uploading attachments to questions"""
    
    class Meta:
        model = QuestionAttachment
        fields = ['file', 'file_type', 'description']
        widgets = {
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'file_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        self.question = kwargs.pop('question', None)
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
        if self.question:
            instance.question = self.question
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
    
    session = forms.ModelChoiceField(
        queryset=Session.objects.none(),
        required=False,
        empty_label="Select a session...",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Select the session where this motion will be tabled"
    )
    
    answer_pdf = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'application/pdf,.pdf',
        }),
        help_text=_("Upload the written answer PDF (required when marking as answered)")
    )

    class Meta:
        model = MotionStatus
        fields = ['status', 'committee', 'session', 'reason', 'answer_pdf']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'committee': forms.Select(attrs={'class': 'form-select'}),
            'session': forms.Select(attrs={'class': 'form-select'}),
            'reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Reason for the status change...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.motion = kwargs.pop('motion', None)
        self.changed_by = kwargs.pop('changed_by', None)
        self.locked_status = kwargs.pop('locked_status', None)  # Status from query parameter
        super().__init__(*args, **kwargs)
        
        # If status is locked (from query parameter), make it read-only
        if self.locked_status:
            self.fields['status'].widget = forms.HiddenInput()
            # Store the locked status value
            self.fields['status'].initial = self.locked_status
            # Set the value attribute on the widget
            self.fields['status'].widget.attrs['value'] = self.locked_status
        
        # Filter committees and sessions to only show those from the same council as the motion's session
        if self.motion and self.motion.session and self.motion.session.council:
            self.fields['committee'].queryset = Committee.objects.filter(
                council=self.motion.session.council,
                is_active=True
            )
            # Filter sessions to only show those from the same council
            self.fields['session'].queryset = Session.objects.filter(
                council=self.motion.session.council
            ).order_by('-scheduled_date')
    
    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        committee = cleaned_data.get('committee')
        
        # If status is locked (from query parameter), use the locked status
        if self.locked_status:
            if status and status != self.locked_status:
                raise forms.ValidationError({
                    'status': 'Status cannot be changed. It must match the selected action.'
                })
            # Ensure status is set to locked_status
            cleaned_data['status'] = self.locked_status
            status = self.locked_status
        
        # If status is 'refer_to_committee', committee is required
        if status == 'refer_to_committee' and not committee:
            raise forms.ValidationError({
                'committee': 'A committee must be selected when referring a motion to committee.'
            })
        
        # If status is 'tabled', session is required
        if status == 'tabled':
            session = cleaned_data.get('session')
            if not session:
                raise forms.ValidationError({
                    'session': 'A session must be selected when tabling a motion.'
                })
        
        # If status is 'voted_in_committee', committee is required and motion must have been previously referred
        if status == 'voted_in_committee':
            if not committee:
                raise forms.ValidationError({
                    'committee': 'A committee must be selected when marking a motion as voted upon in committee.'
                })
            
            if self.motion:
                # Check if motion has ever been in 'refer_to_committee' status
                has_been_referred = MotionStatus.objects.filter(
                    motion=self.motion,
                    status='refer_to_committee'
                ).exists()
                
                # Also check if current status is 'refer_to_committee'
                is_currently_referred = self.motion.status == 'refer_to_committee'
                
                if not (has_been_referred or is_currently_referred):
                    raise forms.ValidationError({
                        'status': 'A motion must be referred to a committee before it can be marked as voted upon in committee.'
                    })
                
                # Validate that the selected committee matches the committee the motion was referred to
                # Get the most recent refer_to_committee status entry
                last_referral = MotionStatus.objects.filter(
                    motion=self.motion,
                    status='refer_to_committee'
                ).order_by('-changed_at').first()
                
                # Check motion's current committee if currently referred
                referral_committee = None
                if is_currently_referred and self.motion.committee:
                    referral_committee = self.motion.committee
                elif last_referral and last_referral.committee:
                    referral_committee = last_referral.committee
                
                # If we found a referral committee, it should match
                if referral_committee and committee != referral_committee:
                    raise forms.ValidationError({
                        'committee': f'This motion was referred to {referral_committee.name}. Please select the same committee.'
                    })
        
        # If status is 'answered', written answer PDF is required
        if status == 'answered':
            answer_pdf = cleaned_data.get('answer_pdf')
            if not answer_pdf:
                raise forms.ValidationError({
                    'answer_pdf': _('Please upload the written answer PDF when marking the motion as answered.')
                })
            # Validate PDF only
            import os
            ext = os.path.splitext(getattr(answer_pdf, 'name', '') or '')[1].lower()
            if ext != '.pdf':
                raise forms.ValidationError({
                    'answer_pdf': _('Only PDF files are allowed for the written answer.')
                })
            # Max size 20MB
            if answer_pdf.size > 20 * 1024 * 1024:
                raise forms.ValidationError({
                    'answer_pdf': _('The file must be smaller than 20 MB.')
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


class QuestionStatusForm(forms.ModelForm):
    """Form for changing question status"""
    
    committee = forms.ModelChoiceField(
        queryset=Committee.objects.filter(is_active=True),
        required=False,
        empty_label="Select a committee...",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Select the committee to refer this question to"
    )
    
    class Meta:
        model = QuestionStatus
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
        self.question = kwargs.pop('question', None)
        self.changed_by = kwargs.pop('changed_by', None)
        super().__init__(*args, **kwargs)
        
        # Filter committees to only show those from the same council as the question's session
        if self.question and self.question.session and self.question.session.council:
            self.fields['committee'].queryset = Committee.objects.filter(
                council=self.question.session.council,
                is_active=True
            )
    
    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        committee = cleaned_data.get('committee')
        
        # If status is 'refer_to_committee', committee is required
        if status == 'refer_to_committee' and not committee:
            raise forms.ValidationError({
                'committee': 'A committee must be selected when referring a question to committee.'
            })
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.question:
            instance.question = self.question
        if self.changed_by:
            instance.changed_by = self.changed_by
        
        if commit:
            instance.save()
        return instance


class QuestionStatusForm(forms.ModelForm):
    """Form for changing question status"""
    
    committee = forms.ModelChoiceField(
        queryset=Committee.objects.filter(is_active=True),
        required=False,
        empty_label="Select a committee...",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Select the committee to refer this question to"
    )
    
    class Meta:
        model = QuestionStatus
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
        self.question = kwargs.pop('question', None)
        self.changed_by = kwargs.pop('changed_by', None)
        super().__init__(*args, **kwargs)
        
        # Filter committees to only show those from the same council as the question's session
        if self.question and self.question.session and self.question.session.council:
            self.fields['committee'].queryset = Committee.objects.filter(
                council=self.question.session.council,
                is_active=True
            )
    
    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        committee = cleaned_data.get('committee')
        
        # If status is 'refer_to_committee', committee is required
        if status == 'refer_to_committee' and not committee:
            raise forms.ValidationError({
                'committee': 'A committee must be selected when referring a question to committee.'
            })
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.question:
            instance.question = self.question
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
        widget=forms.HiddenInput(attrs={'format': '%Y-%m-%d'}),
        help_text="Date of the decision"
    )
    
    decision_time = forms.TimeField(
        widget=forms.HiddenInput(attrs={'format': '%H:%M'}),
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
        from django.utils import timezone
        import datetime
        
        self.motion = kwargs.pop('motion', None)
        self.created_by = kwargs.pop('created_by', None)
        super().__init__(*args, **kwargs)
        
        # Set initial values for date and time to current date and time
        now = timezone.now()
        self.fields['decision_date'].initial = now.date()
        self.fields['decision_time'].initial = now.time()
        
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
        from django.utils import timezone
        import datetime
        
        instance = super().save(commit=False)
        if self.motion:
            instance.motion = self.motion
        if self.created_by:
            instance.created_by = self.created_by
        
        # Combine date and time into decision_time
        decision_date = self.cleaned_data.get('decision_date')
        decision_time = self.cleaned_data.get('decision_time')
        if decision_date and decision_time:
            instance.decision_time = timezone.make_aware(
                datetime.datetime.combine(decision_date, decision_time)
            )
        else:
            # Fallback to current time if date/time are not provided
            instance.decision_time = timezone.now()
        
        if commit:
            instance.save()
        return instance
