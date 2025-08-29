from django.db import models
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
                    'description': f"Default council for {self.name}",
                    'is_active': True
                }
            )


class Council(models.Model):
    """Model representing a council within a local district"""
    name = models.CharField(max_length=200)
    local = models.OneToOneField(Local, on_delete=models.CASCADE, related_name='council')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
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
    council = models.ForeignKey(Council, on_delete=models.CASCADE, related_name='committees', help_text="Council this committee belongs to")
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
        """Number of active members in the committee"""
        return self.members.filter(is_active=True).count()


class CommitteeMember(models.Model):
    """Model representing membership in a committee"""
    ROLE_CHOICES = [
        ('chairperson', 'Chairperson'),
        ('vice_chairperson', 'Vice Chairperson'),
        ('member', 'Member'),
    ]

    committee = models.ForeignKey(Committee, on_delete=models.CASCADE, related_name='members', help_text="Committee the user belongs to")
    user = models.ForeignKey('user.CustomUser', on_delete=models.CASCADE, related_name='committee_memberships', help_text="User who is a member")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member', help_text="Role of the user in the committee")
    joined_date = models.DateField(auto_now_add=True, help_text="Date when the user joined the committee")
    is_active = models.BooleanField(default=True, help_text="Whether the membership is currently active")
    notes = models.TextField(blank=True, help_text="Additional notes about the membership")
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
        return reverse('local:committee-member-detail', args=[str(self.pk)])


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
        ('emergency', 'Emergency Session'),
        ('committee', 'Committee Meeting'),
        ('public_hearing', 'Public Hearing'),
        ('workshop', 'Workshop'),
    ]
    
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('postponed', 'Postponed'),
    ]
    
    title = models.CharField(max_length=200, help_text="Title of the session")
    council = models.ForeignKey(Council, on_delete=models.CASCADE, related_name='sessions', help_text="Council this session belongs to")
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='sessions', blank=True, null=True, help_text="Term this session belongs to")
    session_type = models.CharField(max_length=20, choices=SESSION_TYPE_CHOICES, default='regular', help_text="Type of session")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled', help_text="Current status of the session")
    scheduled_date = models.DateTimeField(help_text="Scheduled date and time of the session")
    start_time = models.TimeField(blank=True, null=True, help_text="Actual start time of the session")
    end_time = models.TimeField(blank=True, null=True, help_text="Actual end time of the session")
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
        return f"{self.title} - {self.council.name}"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('local:session-detail', kwargs={'pk': self.pk})

    def clean(self):
        """Validate that end time is after start time"""
        from django.core.exceptions import ValidationError
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("End time must be after start time")


# Register models for audit logging
auditlog.register(Local)
auditlog.register(Council)
auditlog.register(Committee)
auditlog.register(CommitteeMember)
auditlog.register(Term)
auditlog.register(Party)
auditlog.register(TermSeatDistribution)
auditlog.register(Session)
