from datetime import date

from django.db import models
from django.utils.translation import gettext_lazy as _
from auditlog.registry import auditlog
from auditlog.models import AuditlogHistoryField


class Local(models.Model):
    """Model representing an administrative district (Local)"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True, help_text="Short code for the district")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = AuditlogHistoryField()

    class Meta:
        ordering = ['name']
        verbose_name = "Local"
        verbose_name_plural = "Locals"

    def __str__(self):
        return f"{self.name} ({self.code})"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('local:local-detail', kwargs={'pk': self.pk})

    def save(self, *args, **kwargs):
        """Override save to automatically create a council if one doesn't exist"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Create a default council if this is a new local and no council exists
        if is_new:
            Council.objects.get_or_create(
                local=self,
                defaults={
                    'name': f"Council of {self.name}",
                    'is_active': True
                }
            )


class Council(models.Model):
    """Model representing a council within a local district"""
    name = models.CharField(max_length=200)
    local = models.OneToOneField(Local, on_delete=models.CASCADE, related_name='council')
    is_active = models.BooleanField(default=True)
    calendar_badge_name = models.CharField(
        max_length=80,
        blank=True,
        help_text="Label shown for this council's sessions in the calendar list and monthly calendar (e.g. 'City Council'). Leave empty to use the default 'Council'."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = AuditlogHistoryField()

    class Meta:
        ordering = ['name']
        verbose_name = "Council"
        verbose_name_plural = "Councils"

    def __str__(self):
        return f"{self.name} - {self.local.name}"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('local:council-detail', kwargs={'pk': self.pk})


class Committee(models.Model):
    """Model representing a committee within a council"""
    COMMITTEE_TYPE_CHOICES = [
        ('Ausschuss', 'Ausschuss'),
        ('Kommission', 'Kommission'),
    ]
    
    name = models.CharField(max_length=200, help_text="Name of the committee")
    abbreviation = models.CharField(max_length=20, blank=True, help_text="Abbreviation for the committee (e.g., 'BA' for Budgetausschuss)")
    council = models.ForeignKey(Council, on_delete=models.CASCADE, related_name='committees', help_text="Council this committee belongs to")
    term = models.ForeignKey(
        'Term',
        on_delete=models.SET_NULL,
        related_name='committees',
        null=True,
        blank=True,
        help_text="Term this committee belongs to"
    )
    committee_type = models.CharField(max_length=20, choices=COMMITTEE_TYPE_CHOICES, default='standing', help_text="Type of committee")
    description = models.TextField(blank=True, help_text="Description of the committee's purpose and responsibilities")
    chairperson = models.CharField(max_length=100, blank=True, help_text="Name of the committee chairperson")
    is_active = models.BooleanField(default=True, help_text="Whether the committee is currently active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = AuditlogHistoryField()

    class Meta:
        ordering = ['name']
        verbose_name = "Committee"
        verbose_name_plural = "Committees"
        unique_together = ['name', 'council']

    def __str__(self):
        return f"{self.name} - {self.council.name}"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('local:committee-detail', kwargs={'pk': self.pk})

    @property
    def local(self):
        """Get the local district through the council"""
        return self.council.local

    @property
    def member_count(self):
        """Number of active members in the committee (excluding substitute members)"""
        return self.members.filter(is_active=True).exclude(role='substitute_member').count()

    @property
    def substitute_member_count(self):
        """Number of active substitute members in the committee"""
        return self.members.filter(is_active=True, role='substitute_member').count()

    @property
    def chairperson_member(self):
        """Get the chairperson from committee members"""
        try:
            return self.members.filter(role='chairperson', is_active=True).first()
        except CommitteeMember.DoesNotExist:
            return None
    
    @property
    def chairperson_name(self):
        """Get the chairperson's name from committee members"""
        chairperson = self.chairperson_member
        if chairperson:
            return f"{chairperson.user.first_name} {chairperson.user.last_name}".strip() or chairperson.user.username
        return None

    @property
    def vice_chairperson_member(self):
        """Get the vice chairperson from committee members"""
        try:
            return self.members.filter(role='vice_chairperson', is_active=True).first()
        except CommitteeMember.DoesNotExist:
            return None
    
    @property
    def vice_chairperson_name(self):
        """Get the vice chairperson's name from committee members"""
        vice_chairperson = self.vice_chairperson_member
        if vice_chairperson:
            return f"{vice_chairperson.user.first_name} {vice_chairperson.user.last_name}".strip() or vice_chairperson.user.username
        return None


class CommitteeMeeting(models.Model):
    """Model representing a meeting of a committee (replaces committee sessions)."""
    committee = models.ForeignKey(
        Committee, on_delete=models.CASCADE, related_name='meetings',
        help_text="Committee holding the meeting"
    )
    title = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text="Title or name of the meeting (set automatically on create: committee name + date)"
    )
    scheduled_date = models.DateTimeField(help_text="Date and time when the meeting is scheduled")
    location = models.CharField(max_length=300, blank=True, help_text="Location where the meeting will be held")
    description = models.TextField(blank=True, help_text="Description or agenda of the meeting")
    is_active = models.BooleanField(default=True, help_text="Whether the meeting is currently active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = AuditlogHistoryField()

    class Meta:
        ordering = ['-scheduled_date']
        verbose_name = "Committee Meeting"
        verbose_name_plural = "Committee Meetings"

    def __str__(self):
        return f"{self.title} - {self.committee.name} ({self.scheduled_date.strftime('%Y-%m-%d %H:%M')})"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('local:committee-meeting-detail', kwargs={'pk': self.pk})

    @property
    def is_past(self):
        """Check if the meeting is in the past"""
        from django.utils import timezone
        return self.scheduled_date < timezone.now()


class CommitteeMeetingAttachment(models.Model):
    """Model representing file attachments for committee meetings"""

    ATTACHMENT_TYPE_CHOICES = [
        ('agenda', 'Agenda'),
        ('budget', 'Budget'),
        ('invitation', 'Invitation'),
        ('other', 'Other'),
    ]

    committee_meeting = models.ForeignKey(
        CommitteeMeeting, on_delete=models.CASCADE, related_name='attachments'
    )
    file = models.FileField(upload_to='committee_meeting_attachments/%Y/%m/%d/')
    filename = models.CharField(max_length=255)
    file_type = models.CharField(
        max_length=20, choices=ATTACHMENT_TYPE_CHOICES, default='other'
    )
    description = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        'user.CustomUser', on_delete=models.CASCADE,
        related_name='committee_meeting_attachments'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = "Committee Meeting Attachment"
        verbose_name_plural = "Committee Meeting Attachments"

    def __str__(self):
        return f"{self.filename} - {self.committee_meeting.title}"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse(
            'local:committee-meeting-detail',
            kwargs={'pk': self.committee_meeting.pk}
        )


class CommitteeMember(models.Model):
    """Model representing membership in a committee"""
    ROLE_CHOICES = [
        ('chairperson', _('Chairperson')),
        ('vice_chairperson', _('Vice Chairperson')),
        ('member', _('Member')),
        ('substitute_member', _('Substitute Member')),
    ]

    committee = models.ForeignKey(Committee, on_delete=models.CASCADE, related_name='members', help_text=_("Committee the user belongs to"))
    user = models.ForeignKey('user.CustomUser', on_delete=models.CASCADE, related_name='committee_memberships', help_text=_("User who is a member"))
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member', help_text=_("Role of the user in the committee"))
    joined_date = models.DateField(default=date.today, help_text=_("Date when the user joined the committee"))
    is_active = models.BooleanField(default=True, help_text=_("Whether the membership is currently active"))
    notes = models.TextField(blank=True, help_text=_("Additional notes about the membership"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ['committee', 'user']
        ordering = ['-joined_date']
        verbose_name = "Committee Member"
        verbose_name_plural = "Committee Members"

    def __str__(self):
        return f"{self.user.username} - {self.committee.name} ({self.get_role_display()})"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('local:committee-detail', kwargs={'pk': self.committee.pk})


class CommitteeParticipationSubstitute(models.Model):
    """Records that a substitute member will attend a committee meeting in place of a regular member."""
    committee_meeting = models.ForeignKey(
        CommitteeMeeting,
        on_delete=models.CASCADE,
        related_name='participation_substitutes',
        help_text=_("Committee meeting")
    )
    member = models.ForeignKey(
        CommitteeMember,
        on_delete=models.CASCADE,
        related_name='meeting_substitutions_as_member',
        help_text=_("Regular member who will not attend (replaced by substitute)")
    )
    substitute_member = models.ForeignKey(
        CommitteeMember,
        on_delete=models.CASCADE,
        related_name='meeting_substitutions_as_substitute',
        help_text=_("Substitute member who will attend in place of the member")
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['committee_meeting', 'member'], name='local_committeeparticipation_meeting_member_uniq'),
            models.UniqueConstraint(fields=['committee_meeting', 'substitute_member'], name='local_committeeparticipation_meeting_sub_uniq'),
        ]
        verbose_name = _("Committee participation substitute")
        verbose_name_plural = _("Committee participation substitutes")

    def __str__(self):
        return f"{self.committee_meeting}: {self.member} → {self.substitute_member}"


class Term(models.Model):
    """Model representing a political term/period"""
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    description = models.TextField(blank=True)
    total_seats = models.PositiveIntegerField(default=0, help_text="Total number of seats in this term")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = AuditlogHistoryField()

    class Meta:
        ordering = ['-start_date']
        verbose_name = "Term"
        verbose_name_plural = "Terms"

    def __str__(self):
        return f"{self.name} ({self.start_date.year}-{self.end_date.year})"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('local:term-detail', kwargs={'pk': self.pk})

    @property
    def is_current(self):
        """Check if this term is currently active"""
        from django.utils import timezone
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date

    @property
    def allocated_seats(self):
        """Calculate total allocated seats across all parties"""
        return sum(distribution.seats for distribution in self.seat_distributions.all())


class Party(models.Model):
    """Model representing a political party"""
    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=20, blank=True)
    local = models.ForeignKey(Local, on_delete=models.CASCADE, related_name='parties', null=True, blank=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#007bff', help_text="Hex color code for the party")
    logo = models.ImageField(upload_to='party_logos/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = AuditlogHistoryField()

    class Meta:
        unique_together = ['name', 'local']
        ordering = ['name']
        verbose_name = "Party"
        verbose_name_plural = "Parties"

    def __str__(self):
        return f"{self.name} - {self.local.name}"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('local:party-detail', kwargs={'pk': self.pk})


class TermSeatDistribution(models.Model):
    """Model representing seat distribution for parties within terms"""
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='seat_distributions')
    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name='term_distributions')
    seats = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = AuditlogHistoryField()

    class Meta:
        unique_together = ['term', 'party']
        verbose_name = "Term Seat Distribution"
        verbose_name_plural = "Term Seat Distributions"

    def __str__(self):
        return f"{self.party.name} - {self.seats} seats in {self.term.name}"

    def clean(self):
        """Validate that total seats don't exceed term total"""
        from django.core.exceptions import ValidationError
        if self.seats > self.term.total_seats:
            raise ValidationError(f"Seats cannot exceed term total of {self.term.total_seats}")


class Session(models.Model):
    """Model representing a council session"""
    SESSION_TYPE_CHOICES = [
        ('regular', 'Regular Session'),
        ('special', 'Special Session'),
        ('inaugural', 'Inaugural Session'),
    ]
    
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('invited', 'Invited'),
    ]
    
    title = models.CharField(max_length=200, blank=True, default='', help_text="Title of the session (set automatically on create: Bezirksvertretungssitzung + date)")
    council = models.ForeignKey(Council, on_delete=models.CASCADE, related_name='sessions', help_text="Council this session belongs to")
    committee = models.ForeignKey(Committee, on_delete=models.CASCADE, related_name='sessions', blank=True, null=True, help_text="Committee this session belongs to (optional, for committee meetings)")
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='sessions', blank=True, null=True, help_text="Term this session belongs to")
    session_type = models.CharField(max_length=20, choices=SESSION_TYPE_CHOICES, default='regular', help_text="Type of session")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled', help_text="Current status of the session")
    scheduled_date = models.DateTimeField(help_text="Scheduled date and time of the session")
    location = models.CharField(max_length=200, blank=True, help_text="Location where the session will be held")
    agenda = models.TextField(blank=True, help_text="Agenda items for the session")
    minutes = models.TextField(blank=True, help_text="Minutes from the session")
    notes = models.TextField(blank=True, help_text="Additional notes about the session")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = AuditlogHistoryField()

    class Meta:
        ordering = ['-scheduled_date']
        verbose_name = "Session"
        verbose_name_plural = "Sessions"

    def __str__(self):
        from django.utils import timezone
        from django.utils.formats import date_format
        return f"{self.title} - {date_format(self.scheduled_date, 'SHORT_DATE_FORMAT')}"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('local:session-detail', kwargs={'pk': self.pk})


class SessionAttachment(models.Model):
    """Model representing file attachments for sessions"""
    
    ATTACHMENT_TYPE_CHOICES = [
        ('agenda', 'Agenda'),
        ('budget', 'Budget'),
        ('invitation', 'Invitation'),
        ('other', 'Other'),
    ]
    
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='session_attachments/%Y/%m/%d/')
    filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=20, choices=ATTACHMENT_TYPE_CHOICES, default='document')
    description = models.TextField(blank=True)
    uploaded_by = models.ForeignKey('user.CustomUser', on_delete=models.CASCADE, related_name='session_attachments')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = "Session Attachment"
        verbose_name_plural = "Session Attachments"
    
    def __str__(self):
        return f"{self.filename} - {self.session.title}"
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('local:session-attachment-detail', kwargs={'pk': self.pk})


class SessionPresence(models.Model):
    """Model representing presence tracking for parties in a session"""
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='presence_records')
    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name='session_presence')
    present_count = models.PositiveIntegerField(default=0, help_text="Number of present members from this party")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = AuditlogHistoryField()

    class Meta:
        unique_together = ['session', 'party']
        verbose_name = "Session Presence"
        verbose_name_plural = "Session Presences"
        ordering = ['party__name']

    def __str__(self):
        return f"{self.party.name} - {self.present_count} present in {self.session.title}"


# Register models for audit logging
auditlog.register(Local)
auditlog.register(Council)
auditlog.register(Committee)
auditlog.register(CommitteeMeeting)
auditlog.register(CommitteeMeetingAttachment)
auditlog.register(CommitteeMember)
auditlog.register(CommitteeParticipationSubstitute)
auditlog.register(Term)
auditlog.register(Party)
auditlog.register(TermSeatDistribution)
auditlog.register(Session)
auditlog.register(SessionAttachment)
auditlog.register(SessionPresence)
