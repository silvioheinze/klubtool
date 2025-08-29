from django.db import models
from django.contrib.auth import get_user_model
from auditlog.registry import auditlog
from local.models import Session, Party
from group.models import Group

User = get_user_model()


class Motion(models.Model):
    """Model representing a motion in a council session"""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ]
    
    MOTION_TYPE_CHOICES = [
        ('resolution', 'Resolution'),
        ('general', 'General motion'),
    ]
    

    
    # Basic Information
    title = models.CharField(max_length=200, help_text="Title of the motion")
    description = models.TextField(help_text="Detailed description of the motion")
    motion_type = models.CharField(max_length=20, choices=MOTION_TYPE_CHOICES, default='proposal')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Relationships
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='motions', help_text="Session where this motion will be presented")
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


class MotionVote(models.Model):
    """Model representing votes on motions"""
    
    VOTE_CHOICES = [
        ('yes', 'Yes'),
        ('no', 'No'),
        ('abstain', 'Abstain'),
        ('absent', 'Absent'),
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


# Register models for audit logging
auditlog.register(Motion)
auditlog.register(MotionVote)
auditlog.register(MotionComment)
auditlog.register(MotionAttachment)
