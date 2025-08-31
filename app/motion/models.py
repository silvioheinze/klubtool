from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from auditlog.registry import auditlog
from local.models import Session, Party
from group.models import Group

User = get_user_model()


class Motion(models.Model):
    """Model representing a motion in a council session"""
    
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('submitted', _('Submitted')),
        ('refer_to_committee', _('Refer to Committee')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
        ('withdrawn', _('Withdrawn')),
    ]
    
    MOTION_TYPE_CHOICES = [
        ('resolution', _('Resolution')),
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
    

    
    # Metadata
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='submitted_motions')
    submitted_date = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
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
        return self.status == 'draft'
    
    @property
    def session_date(self):
        """Get the session date"""
        return self.session.scheduled_date if self.session else None
    
    def save(self, *args, **kwargs):
        """Override save to track status changes"""
        if self.pk:  # Only for existing instances
            try:
                old_instance = Motion.objects.get(pk=self.pk)
                if old_instance.status != self.status:
                    # Status has changed, create a status history entry
                    MotionStatus.objects.create(
                        motion=self,
                        status=self.status,
                        committee=getattr(self, '_status_committee', None),
                        changed_by=getattr(self, '_status_changed_by', None),
                        reason=getattr(self, '_status_change_reason', '')
                    )
            except Motion.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)


class MotionVote(models.Model):
    """Model representing votes on motions by parties"""
    
    VOTE_CHOICES = [
        ('approve', _('Approve')),
        ('reject', _('Reject')),
        ('abstain', _('Abstain')),
    ]
    
    motion = models.ForeignKey(Motion, on_delete=models.CASCADE, related_name='votes')
    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name='motion_votes', help_text="Party casting the vote")
    status = models.ForeignKey('MotionStatus', on_delete=models.CASCADE, related_name='votes', null=True, blank=True, help_text="Status change this vote is connected to")
    approve_votes = models.PositiveIntegerField(default=0, help_text="Number of approve votes from this party")
    reject_votes = models.PositiveIntegerField(default=0, help_text="Number of reject votes from this party")
    abstain_votes = models.PositiveIntegerField(default=0, help_text="Number of abstain votes from this party")
    notes = models.TextField(blank=True, help_text="Additional notes about the voting")
    voted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-voted_at']
        verbose_name = "Motion Vote"
        verbose_name_plural = "Motion Votes"
    
    def __str__(self):
        return f"{self.party.name} - {self.get_vote_summary()} on {self.motion.title}"
    
    def get_vote_summary(self):
        """Get a summary of the voting results"""
        total_votes = self.approve_votes + self.reject_votes + self.abstain_votes
        if total_votes == 0:
            return "No votes cast"
        
        if self.approve_votes > self.reject_votes:
            return f"Approve ({self.approve_votes}/{total_votes})"
        elif self.reject_votes > self.approve_votes:
            return f"Reject ({self.reject_votes}/{total_votes})"
        else:
            return f"Tie ({self.approve_votes}-{self.reject_votes}-{self.abstain_votes})"
    
    @property
    def total_votes_cast(self):
        """Total number of votes cast"""
        return self.approve_votes + self.reject_votes + self.abstain_votes
    
    @property
    def participation_rate(self):
        """Percentage of party members who voted - simplified without total_members"""
        return 100  # Since we removed total_members, assume 100% participation
    
    def clean(self):
        """Validate the vote data"""
        from django.core.exceptions import ValidationError
        # No validation needed since we removed total_members constraint
        pass


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
    committee = models.ForeignKey('local.Committee', on_delete=models.SET_NULL, null=True, blank=True, related_name='motion_status_changes', help_text="Committee when status is 'refer_to_committee'")
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='motion_status_changes')
    changed_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True, help_text="Reason for the status change")
    
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


# Register models for audit logging
auditlog.register(Motion)
auditlog.register(MotionVote)
auditlog.register(MotionComment)
auditlog.register(MotionAttachment)
auditlog.register(MotionStatus)
auditlog.register(MotionGroupDecision)
