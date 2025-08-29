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
        """Get total number of allocated seats across all parties"""
        return self.seat_distributions.aggregate(
            total=models.Sum('seats')
        )['total'] or 0

    @property
    def unallocated_seats(self):
        """Get number of unallocated seats"""
        return self.total_seats - self.allocated_seats

    @property
    def seat_distribution_summary(self):
        """Get a summary of seat distribution"""
        distributions = self.seat_distributions.select_related('party').all()
        return [f"{d.party.name}: {d.seats}" for d in distributions]


class Party(models.Model):
    """Model representing a political party"""
    name = models.CharField(max_length=200)
    short_name = models.CharField(max_length=50, blank=True)
    local = models.ForeignKey(Local, on_delete=models.CASCADE, related_name='parties', null=True, blank=True, help_text="Local district this party belongs to")
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, blank=True, help_text="Hex color code (e.g., #FF0000)")
    logo = models.ImageField(upload_to='party_logos/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = AuditlogHistoryField()

    class Meta:
        ordering = ['name']
        verbose_name = "Party"
        verbose_name_plural = "Parties"
        unique_together = ['name', 'local']  # Party names must be unique within a local (when local is not null)

    def __str__(self):
        return f"{self.name} ({self.local.name})"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('local:party-detail', kwargs={'pk': self.pk})

    def get_seats_in_term(self, term):
        """Get number of seats for this party in a specific term"""
        try:
            distribution = self.term_seats.get(term=term)
            return distribution.seats
        except TermSeatDistribution.DoesNotExist:
            return 0


class TermSeatDistribution(models.Model):
    """Model representing seat distribution of parties in a term"""
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='seat_distributions')
    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name='term_seats')
    seats = models.PositiveIntegerField(default=0)
    percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        blank=True, 
        null=True,
        help_text="Percentage of total seats (auto-calculated)"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = AuditlogHistoryField()

    class Meta:
        ordering = ['-seats', 'party__name']
        verbose_name = "Term Seat Distribution"
        verbose_name_plural = "Term Seat Distributions"
        unique_together = ['term', 'party']

    def __str__(self):
        return f"{self.party.name}: {self.seats} seats in {self.term.name}"

    def save(self, *args, **kwargs):
        """Auto-calculate percentage when seats are updated"""
        if self.term.total_seats > 0:
            self.percentage = (self.seats / self.term.total_seats) * 100
        else:
            self.percentage = None
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('local:term-seat-detail', kwargs={'pk': self.pk})


class Session(models.Model):
    """Model representing a council session"""
    SESSION_TYPES = [
        ('regular', 'Regular Session'),
        ('special', 'Special Session'),
        ('emergency', 'Emergency Session'),
        ('committee', 'Committee Meeting'),
    ]
    
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('postponed', 'Postponed'),
    ]

    title = models.CharField(max_length=200)
    council = models.ForeignKey(Council, on_delete=models.CASCADE, related_name='sessions')
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='sessions')
    session_type = models.CharField(max_length=20, choices=SESSION_TYPES, default='regular')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    scheduled_date = models.DateTimeField()
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    location = models.CharField(max_length=200, blank=True)
    agenda = models.TextField(blank=True)
    minutes = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = AuditlogHistoryField()

    class Meta:
        ordering = ['-scheduled_date']
        verbose_name = "Session"
        verbose_name_plural = "Sessions"

    def __str__(self):
        return f"{self.title} - {self.council.name} ({self.scheduled_date.strftime('%Y-%m-%d')})"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('local:session-detail', kwargs={'pk': self.pk})

    @property
    def is_upcoming(self):
        """Check if this session is in the future"""
        from django.utils import timezone
        return self.scheduled_date > timezone.now()

    @property
    def is_past(self):
        """Check if this session is in the past"""
        from django.utils import timezone
        return self.scheduled_date < timezone.now()


# Register all models for audit logging
auditlog.register(Local)
auditlog.register(Council)
auditlog.register(Term)
auditlog.register(Party)
auditlog.register(TermSeatDistribution)
auditlog.register(Session)
