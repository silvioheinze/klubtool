from django.db import models
from django.contrib.auth import get_user_model
from auditlog.registry import auditlog
from local.models import Party

User = get_user_model()

class Group(models.Model):
    """Political group within a party"""
    name = models.CharField(max_length=200, help_text="Name of the political group")
    short_name = models.CharField(max_length=50, blank=True, help_text="Short name or abbreviation")
    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name='groups', help_text="Party this group belongs to")
    description = models.TextField(blank=True, help_text="Description of the group's purpose and goals")
    founded_date = models.DateField(null=True, blank=True, help_text="Date when the group was founded")
    is_active = models.BooleanField(default=True, help_text="Whether the group is currently active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ['name', 'party']
        ordering = ['name']
        verbose_name = "Political Group"
        verbose_name_plural = "Political Groups"

    def __str__(self):
        return f"{self.name} ({self.party.name})"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('group:group-detail', args=[str(self.pk)])

    @property
    def member_count(self):
        """Number of active members in the group"""
        return self.members.filter(is_active=True).count()

    @property
    def local(self):
        """Get the local district through the party"""
        return self.party.local

class GroupMember(models.Model):
    """Membership of a user in a political group"""
    ROLE_CHOICES = [
        ('member', 'Member'),
        ('leader', 'Leader'),
        ('deputy_leader', 'Deputy Leader'),
        ('secretary', 'Secretary'),
        ('treasurer', 'Treasurer'),
        ('board_member', 'Board Member'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_memberships', help_text="User who is a member")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='members', help_text="Group the user belongs to")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member', help_text="Role of the user in the group")
    joined_date = models.DateField(auto_now_add=True, help_text="Date when the user joined the group")
    is_active = models.BooleanField(default=True, help_text="Whether the membership is currently active")
    notes = models.TextField(blank=True, help_text="Additional notes about the membership")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ['user', 'group']
        ordering = ['-joined_date']
        verbose_name = "Group Member"
        verbose_name_plural = "Group Members"

    def __str__(self):
        return f"{self.user.username} - {self.group.name} ({self.get_role_display()})"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('group:member-detail', args=[str(self.pk)])

# Register models for audit logging
auditlog.register(Group)
auditlog.register(GroupMember)
