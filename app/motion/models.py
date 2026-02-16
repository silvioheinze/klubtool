from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from auditlog.registry import auditlog
from local.models import Session, Party
from group.models import Group

User = get_user_model()


class Tag(models.Model):
    """Model representing a tag for categorizing motions and inquiries"""
    name = models.CharField(max_length=50, unique=True, help_text="Name of the tag")
    slug = models.SlugField(max_length=50, unique=True, help_text="URL-friendly version of the tag name")
    color = models.CharField(max_length=7, default='#007bff', help_text="Color code for the tag (hex format)")
    description = models.TextField(blank=True, help_text="Description of the tag")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Tag"
        verbose_name_plural = "Tags"
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """Auto-generate slug from name if not provided"""
        from django.utils.text import slugify
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Motion(models.Model):
    """Model representing a motion in a council session"""
    
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('submitted', _('Submitted')),
        ('tabled', _('Tabled')),
        ('refer_to_committee', _('Refer to Committee')),
        ('refer_no_majority', _('Refer to Committee (no majority)')),
        ('voted_in_committee', _('Voted upon in Committee')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
        ('withdrawn', _('Withdrawn')),
        ('not_admitted', _('Nicht zugelassen')),
        ('answered', _('Answered')),
        ('deleted', _('Deleted')),
    ]
    
    MOTION_TYPE_CHOICES = [
        ('resolution', _('Resolutionsantrag')),
        ('general', _('General motion')),
    ]
    

    
    # Basic Information
    title = models.CharField(max_length=200, help_text="Title of the motion")
    text = models.TextField(blank=True, help_text="Detailed text of the motion")
    rationale = models.TextField(blank=True, help_text="Rationale and justification for the motion")
    motion_type = models.CharField(max_length=20, choices=MOTION_TYPE_CHOICES, default='general')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Relationships
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='motions', help_text="Session where this motion will be presented")
    committee = models.ForeignKey('local.Committee', on_delete=models.CASCADE, related_name='motions', blank=True, null=True, help_text="Committee this motion is assigned to (optional)")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='motions', help_text="Group proposing this motion")
    parties = models.ManyToManyField(Party, related_name='motions', blank=True, help_text="Parties supporting this motion")
    interventions = models.ManyToManyField(User, related_name='motion_interventions', blank=True, help_text=_("Wortmeldung: Users from the corresponding group who can speak in session"))
    tags = models.ManyToManyField('Tag', related_name='motions', blank=True, help_text="Tags for categorizing this motion")
    

    
    # Metadata
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='submitted_motions')
    submitted_date = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    session_rank = models.PositiveIntegerField(default=0, help_text="Rank/order of this motion within its session")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-submitted_date']
        verbose_name = "Motion"
        verbose_name_plural = "Motions"
    
    def __str__(self):
        return f"{self.title} - {self.group.name}"
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('motion:motion-detail', args=[str(self.pk)])
    
    @property
    def supporting_parties_count(self):
        """Number of parties supporting this motion"""
        return self.parties.count()
    

    
    @property
    def can_be_edited(self):
        """Check if motion can still be edited"""
        return True  # Motions can be edited regardless of status
    
    def can_be_deleted_by(self, user):
        """Check if a user can delete this motion"""
        # Superusers can delete any motion
        if user.is_superuser:
            return True
        
        # Users can delete their own motions
        if self.submitted_by == user:
            return True
        
        # Group admins can delete motions from their groups
        if self.group:
            from group.models import GroupMember
            from user.models import Role
            
            try:
                # Get leader and deputy leader roles
                leader_role = Role.objects.get(name='Leader')
                deputy_leader_role = Role.objects.get(name='Deputy Leader')
                
                # Check if user has these roles in the motion's group
                membership = GroupMember.objects.filter(
                    user=user,
                    group=self.group,
                    is_active=True,
                    roles__in=[leader_role, deputy_leader_role]
                ).first()
                
                return membership is not None
            except Role.DoesNotExist:
                return False
        
        return False
    
    @property
    def session_date(self):
        """Get the session date"""
        return self.session.scheduled_date if self.session else None
    
    def save(self, *args, **kwargs):
        """Override save to track status changes"""
        if self.pk:  # Only for existing instances
            try:
                old_instance = Motion.objects.get(pk=self.pk)
                old_status = old_instance.status
                if old_status != self.status:
                    # Status has changed, create a status history entry
                    MotionStatus.objects.create(
                        motion=self,
                        status=self.status,
                        committee=getattr(self, '_status_committee', None),
                        session=getattr(self, '_status_session', None),
                        changed_by=getattr(self, '_status_changed_by', None),
                        reason=getattr(self, '_status_change_reason', '')
                    )
                    # Log the status change
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug(f"Motion {self.pk} status changed from {old_status} to {self.status}")
            except Motion.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)


class MotionVote(models.Model):
    """Model representing votes on motions by parties"""
    
    VOTE_TYPE_CHOICES = [
        ('regular', _('Regular Vote')),
        ('refer_to_committee', _('Refer to Committee')),
    ]
    
    VOTE_CHOICES = [
        ('approve', _('Approve')),
        ('reject', _('Reject')),
    ]
    
    motion = models.ForeignKey(Motion, on_delete=models.CASCADE, related_name='votes')
    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name='motion_votes', help_text="Party casting the vote")
    vote_type = models.CharField(max_length=20, choices=VOTE_TYPE_CHOICES, default='regular', help_text="Type of vote: regular or refer to committee")
    status = models.ForeignKey('MotionStatus', on_delete=models.CASCADE, related_name='votes', null=True, blank=True, help_text="Status change this vote is connected to")
    approve_votes = models.PositiveIntegerField(default=0, help_text="Number of votes in favor from this party")
    reject_votes = models.PositiveIntegerField(default=0, help_text="Number of votes against from this party")
    notes = models.TextField(blank=True, help_text="Additional notes about the voting")
    voted_at = models.DateTimeField(auto_now_add=True)
    
    # New fields for multiple votes support
    vote_session = models.ForeignKey(
        'local.Session',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='motion_votes',
        help_text="Session where this vote was cast"
    )
    vote_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Custom name/description for this voting round"
    )
    outcome = models.CharField(
        max_length=20,
        choices=[
            ('adopted', 'Adopted'),
            ('rejected', 'Rejected'),
            ('tie', 'Tie'),
            ('referred', 'Referred to Committee'),
            ('not_referred', 'Not Referred'),
        ],
        blank=True,
        help_text="Calculated outcome based on majority"
    )
    total_favor = models.PositiveIntegerField(
        default=0,
        help_text="Total votes in favor across all parties (calculated)"
    )
    total_against = models.PositiveIntegerField(
        default=0,
        help_text="Total votes against across all parties (calculated)"
    )
    
    class Meta:
        ordering = ['-voted_at']
        verbose_name = "Motion Vote"
        verbose_name_plural = "Motion Votes"
    
    def __str__(self):
        # Safely get party name without triggering RelatedObjectDoesNotExist
        try:
            if hasattr(self, 'party_id') and self.party_id:
                # Use getattr with default to avoid RelatedObjectDoesNotExist
                party = getattr(self, 'party', None)
                if party:
                    party_name = party.name
                else:
                    party_name = f"Party {self.party_id}"
            else:
                party_name = "Unknown Party"
        except Exception:
            party_name = "Unknown Party"
        
        # Safely get motion title
        try:
            if hasattr(self, 'motion_id') and self.motion_id:
                # Use getattr with default to avoid RelatedObjectDoesNotExist
                motion = getattr(self, 'motion', None)
                if motion:
                    motion_title = motion.title
                else:
                    motion_title = f"Motion {self.motion_id}"
            else:
                motion_title = "Unknown Motion"
        except Exception:
            motion_title = "Unknown Motion"
        
        return f"{party_name} - {self.get_vote_summary()} on {motion_title}"
    
    def get_vote_summary(self):
        """Get a summary of the voting results"""
        total_votes = self.approve_votes + self.reject_votes
        if total_votes == 0:
            return "No votes cast"
        
        if self.approve_votes > self.reject_votes:
            return f"Approve ({self.approve_votes}/{total_votes})"
        elif self.reject_votes > self.approve_votes:
            return f"Reject ({self.reject_votes}/{total_votes})"
        else:
            return f"Tie ({self.approve_votes}-{self.reject_votes})"
    
    @property
    def total_votes_cast(self):
        """Total number of votes cast"""
        return self.approve_votes + self.reject_votes
    
    @property
    def participation_rate(self):
        """Percentage of party members who voted - simplified without total_members"""
        return 100  # Since we removed total_members, assume 100% participation
    
    def calculate_outcome(self):
        """Calculate and return the outcome based on vote totals"""
        if self.vote_type == 'regular':
            if self.total_favor > self.total_against:
                return 'adopted'
            elif self.total_against > self.total_favor:
                return 'rejected'
            else:
                return 'tie'
        elif self.vote_type == 'refer_to_committee':
            if self.total_favor > self.total_against:
                return 'referred'
            else:
                return 'not_referred'
        return ''
    
    def clean(self):
        """Validate the vote data"""
        from django.core.exceptions import ValidationError
        from django.utils import timezone
        from local.models import Term, TermSeatDistribution
        
        # Get the motion's session and term (use motion_id to avoid RelatedObjectDoesNotExist)
        if not self.motion_id:
            return
        try:
            motion = self.motion
        except Motion.DoesNotExist:
            return
        if not motion or not getattr(motion, 'session_id', None):
            return
        try:
            session = motion.session
        except Exception:
            return
        term = session.term
        
        # If session doesn't have a term, try to get current term from local
        if not term and session.council and session.council.local:
            today = timezone.now().date()
            term = Term.objects.filter(
                start_date__lte=today,
                end_date__gte=today,
                is_active=True
            ).first()
        
        # Validate votes don't exceed party's max seats
        # Use party_id to avoid RelatedObjectDoesNotExist when instance is unsaved
        if term and self.party_id:
            try:
                from local.models import Party
                party = Party.objects.get(pk=self.party_id)
                seat_distribution = TermSeatDistribution.objects.get(
                    term=term,
                    party=party
                )
                max_seats = seat_distribution.seats
                total_votes = (self.approve_votes or 0) + (self.reject_votes or 0)
                
                if total_votes > max_seats:
                    raise ValidationError(
                        _('Total votes (%(total)d) cannot exceed party\'s maximum seats (%(max)d) for this term.') % {
                            'total': total_votes,
                            'max': max_seats
                        }
                    )
            except Party.DoesNotExist:
                pass
            except TermSeatDistribution.DoesNotExist:
                # If no seat distribution exists, we can't validate
                pass
    
    def save(self, *args, **kwargs):
        """Override save to calculate outcome and totals"""
        # Save first to get pk
        super().save(*args, **kwargs)
        
        # After saving, recalculate totals for all votes in this round
        if self.motion and self.vote_type:
            all_votes = MotionVote.objects.filter(
                motion=self.motion,
                vote_type=self.vote_type,
                vote_name=self.vote_name or ''
            )
            total_favor = sum(v.approve_votes for v in all_votes)
            total_against = sum(v.reject_votes for v in all_votes)
            
            # Calculate outcome based on vote type
            if self.vote_type == 'regular':
                if total_favor > total_against:
                    outcome = 'adopted'
                elif total_against > total_favor:
                    outcome = 'rejected'
                else:
                    outcome = 'tie'
            elif self.vote_type == 'refer_to_committee':
                if total_favor > total_against:
                    outcome = 'referred'
                else:
                    outcome = 'not_referred'
            else:
                outcome = ''
            
            # Update all votes in this round with the same totals and outcome
            all_votes.update(
                total_favor=total_favor,
                total_against=total_against,
                outcome=outcome
            )


class MotionComment(models.Model):
    """Model representing comments on motions"""
    
    motion = models.ForeignKey(Motion, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='motion_comments')
    content = models.TextField()
    is_public = models.BooleanField(default=True, help_text="Whether this comment is visible to all users")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
        verbose_name = "Motion Comment"
        verbose_name_plural = "Motion Comments"
    
    def __str__(self):
        return f"Comment by {self.author.username} on {self.motion.title}"


class MotionAttachment(models.Model):
    """Model representing file attachments for motions"""
    
    ATTACHMENT_TYPE_CHOICES = [
        ('document', 'Document'),
        ('image', 'Image'),
        ('spreadsheet', 'Spreadsheet'),
        ('presentation', 'Presentation'),
        ('other', 'Other'),
    ]
    
    motion = models.ForeignKey(Motion, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='motion_attachments/%Y/%m/%d/')
    filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=20, choices=ATTACHMENT_TYPE_CHOICES, default='document')
    description = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='motion_attachments')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = "Motion Attachment"
        verbose_name_plural = "Motion Attachments"
    
    def __str__(self):
        return f"{self.filename} - {self.motion.title}"


class MotionStatus(models.Model):
    """Model representing status changes for motions"""
    
    motion = models.ForeignKey(Motion, on_delete=models.CASCADE, related_name='status_history')
    status = models.CharField(max_length=20, choices=Motion.STATUS_CHOICES)
    committee = models.ForeignKey('local.Committee', on_delete=models.SET_NULL, null=True, blank=True, related_name='motion_status_changes', help_text="Committee when status is 'refer_to_committee' or 'voted_in_committee'")
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True, blank=True, related_name='motion_status_changes', help_text="Session when status is 'tabled'")
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='motion_status_changes')
    changed_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True, help_text="Reason for the status change")
    answer_pdf = models.FileField(
        upload_to='motion_answers/%Y/%m/%d/',
        null=True,
        blank=True,
        help_text=_("Written answer PDF (when status is 'answered')")
    )
    
    class Meta:
        ordering = ['-changed_at']
        verbose_name = "Motion Status"
        verbose_name_plural = "Motion Statuses"
    
    def __str__(self):
        return f"{self.motion.title} - {self.get_status_display()} ({self.changed_at.strftime('%d.%m.%Y %H:%M')})"


class MotionGroupDecision(models.Model):
    """Model representing group decisions on motions"""
    
    DECISION_CHOICES = [
        ('approve', _('Approve')),
        ('reject', _('Reject')),
        ('abstain', _('Abstain')),
        ('withdraw', _('Withdraw')),
        ('refer_to_committee', _('Refer to Committee')),
    ]
    
    motion = models.ForeignKey(Motion, on_delete=models.CASCADE, related_name='group_decisions')
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES)
    committee = models.ForeignKey('local.Committee', on_delete=models.SET_NULL, null=True, blank=True, related_name='motion_group_decisions', help_text="Committee when decision is 'refer_to_committee'")
    description = models.TextField(blank=True, help_text="Description of the group decision")
    decision_time = models.DateTimeField(help_text="When the decision was made")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='motion_group_decisions_created')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-decision_time']
        verbose_name = "Motion Group Decision"
        verbose_name_plural = "Motion Group Decisions"
    
    def __str__(self):
        return f"{self.motion.title} - {self.get_decision_display()} ({self.decision_time.strftime('%d.%m.%Y %H:%M')})"


class Inquiry(models.Model):
    """Model representing an inquiry (Anfrage) in a council session"""
    
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('submitted', _('Submitted')),
        ('refer_to_committee', _('Refer to Committee')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
        ('answered', _('Answered')),
        ('withdrawn', _('Withdrawn')),
        ('not_admitted', _('Nicht zugelassen')),
    ]
    
    # Basic Information
    title = models.CharField(max_length=200, help_text="Title of the inquiry")
    text = models.TextField(blank=True, help_text="Detailed text of the inquiry")
    answer = models.TextField(blank=True, help_text="Answer to the inquiry")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Relationships
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='inquiries', help_text="Session where this inquiry will be presented")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='inquiries', help_text="Group asking this inquiry")
    parties = models.ManyToManyField(Party, related_name='inquiries', blank=True, help_text="Parties supporting this inquiry")
    interventions = models.ManyToManyField(User, related_name='inquiry_interventions', blank=True, help_text=_("Wortmeldung: Users from the corresponding group who can speak in session"))
    tags = models.ManyToManyField('Tag', related_name='inquiries', blank=True, help_text="Tags for categorizing this inquiry")
    
    # Metadata
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='submitted_inquiries')
    submitted_date = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    session_rank = models.PositiveIntegerField(default=0, help_text="Rank/order of this inquiry within its session")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-submitted_date']
        verbose_name = "Inquiry"
        verbose_name_plural = "Inquiries"
    
    def __str__(self):
        return f"{self.title} - {self.group.name}"
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('inquiry:inquiry-detail', args=[str(self.pk)])
    
    @property
    def supporting_parties_count(self):
        """Number of parties supporting this inquiry"""
        return self.parties.count()
    
    @property
    def can_be_edited(self):
        """Check if inquiry can still be edited"""
        return True  # Inquiries can be edited regardless of status
    
    def can_be_deleted_by(self, user):
        """Check if a user can delete this inquiry"""
        # Superusers can delete any inquiry
        if user.is_superuser:
            return True
        
        # Users can delete their own inquiries
        if self.submitted_by == user:
            return True
        
        # Group admins can delete inquiries from their groups
        if self.group:
            from group.models import GroupMember
            from user.models import Role
            
            try:
                # Get leader and deputy leader roles
                leader_role = Role.objects.get(name='Leader')
                deputy_leader_role = Role.objects.get(name='Deputy Leader')
                
                # Check if user has these roles in the inquiry's group
                membership = GroupMember.objects.filter(
                    user=user,
                    group=self.group,
                    is_active=True,
                    roles__in=[leader_role, deputy_leader_role]
                ).first()
                
                return membership is not None
            except Role.DoesNotExist:
                return False
        
        return False
    
    @property
    def session_date(self):
        """Get the session date"""
        return self.session.scheduled_date if self.session else None
    
    def save(self, *args, **kwargs):
        """Override save to track status changes"""
        if self.pk:  # Only for existing instances
            try:
                old_instance = Inquiry.objects.get(pk=self.pk)
                if old_instance.status != self.status:
                    # Status has changed, create a status history entry
                    InquiryStatus.objects.create(
                        inquiry=self,
                        status=self.status,
                        committee=getattr(self, '_status_committee', None),
                        changed_by=getattr(self, '_status_changed_by', None),
                        reason=getattr(self, '_status_change_reason', '')
                    )
            except Inquiry.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)


class InquiryStatus(models.Model):
    """Model representing status changes for inquiries"""
    
    inquiry = models.ForeignKey(Inquiry, on_delete=models.CASCADE, related_name='status_history')
    status = models.CharField(max_length=20, choices=Inquiry.STATUS_CHOICES)
    committee = models.ForeignKey('local.Committee', on_delete=models.SET_NULL, null=True, blank=True, related_name='inquiry_status_changes', help_text="Committee when status is 'refer_to_committee'")
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='inquiry_status_changes')
    changed_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True, help_text="Reason for the status change")
    
    class Meta:
        ordering = ['-changed_at']
        verbose_name = "Inquiry Status"
        verbose_name_plural = "Inquiry Statuses"
    
    def __str__(self):
        return f"{self.inquiry.title} - {self.get_status_display()} ({self.changed_at.strftime('%d.%m.%Y %H:%M')})"


class InquiryAttachment(models.Model):
    """Model representing file attachments for inquiries"""
    
    ATTACHMENT_TYPE_CHOICES = [
        ('document', 'Document'),
        ('image', 'Image'),
        ('spreadsheet', 'Spreadsheet'),
        ('presentation', 'Presentation'),
        ('other', 'Other'),
    ]
    
    inquiry = models.ForeignKey(Inquiry, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='inquiry_attachments/%Y/%m/%d/')
    filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=20, choices=ATTACHMENT_TYPE_CHOICES, default='document')
    description = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='inquiry_attachments')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = "Inquiry Attachment"
        verbose_name_plural = "Inquiry Attachments"
    
    def __str__(self):
        return f"{self.filename} - {self.inquiry.title}"


# Register models for audit logging
auditlog.register(Tag)
auditlog.register(Motion)
auditlog.register(MotionVote)
auditlog.register(MotionComment)
auditlog.register(MotionAttachment)
auditlog.register(MotionStatus)
auditlog.register(MotionGroupDecision)
auditlog.register(Inquiry)
auditlog.register(InquiryStatus)
auditlog.register(InquiryAttachment)
