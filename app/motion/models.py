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
        return self.status in ['draft', 'submitted', 'under_review']
    
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
    """Model representing votes on motions"""
    
    VOTE_CHOICES = [
        ('yes', _('Yes')),
        ('no', _('No')),
        ('abstain', _('Abstain')),
        ('absent', _('Absent')),
    ]
    
    motion = models.ForeignKey(Motion, on_delete=models.CASCADE, related_name='votes')
    voter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='motion_votes')
    vote = models.CharField(max_length=10, choices=VOTE_CHOICES)
    reason = models.TextField(blank=True, help_text="Reason for the vote")
    voted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['motion', 'voter']
        ordering = ['-voted_at']
        verbose_name = "Motion Vote"
        verbose_name_plural = "Motion Votes"
    
    def __str__(self):
        return f"{self.voter.username} - {self.get_vote_display()} on {self.motion.title}"


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
