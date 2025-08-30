from django.db import models
from django.contrib.auth import get_user_model
from auditlog.registry import auditlog
from local.models import Party
from django.utils import timezone
from user.models import Role

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

    def get_group_admins(self):
        """Get all group admin members"""
        return self.members.filter(roles__name='Group Admin', is_active=True)

    def has_group_admin(self, user):
        """Check if a user is a group admin of this group"""
        return self.members.filter(user=user, roles__name='Group Admin', is_active=True).exists()

    def can_user_manage_group(self, user):
        """Check if a user can manage this group (superuser or group admin)"""
        if user.is_superuser:
            return True
        return self.has_group_admin(user)




class GroupMember(models.Model):
    """Membership of a user in a political group"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_memberships', help_text="User who is a member")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='members', help_text="Group the user belongs to")
    roles = models.ManyToManyField(Role, related_name='group_memberships', help_text="Roles of the user in the group")
    joined_date = models.DateField(default=timezone.now, help_text="Date when the user joined the group")
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
        roles_display = ', '.join([role.name for role in self.roles.all()])
        return f"{self.user.username} - {self.group.name} ({roles_display})"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('group:member-detail', args=[str(self.pk)])

    @property
    def is_group_admin(self):
        """Check if this member is a group admin"""
        return self.roles.filter(name='Group Admin').exists()

    @property
    def is_leader(self):
        """Check if this member is a leader"""
        return self.roles.filter(name='Leader').exists()

    @property
    def is_deputy_leader(self):
        """Check if this member is a deputy leader"""
        return self.roles.filter(name='Deputy Leader').exists()



    @property
    def is_board_member(self):
        """Check if this member is a board member"""
        return self.roles.filter(name='Board Member').exists()

    def has_role(self, role_name):
        """Check if this member has a specific role"""
        return self.roles.filter(name=role_name).exists()

    def get_roles_display(self):
        """Get a formatted string of all roles"""
        return ', '.join([role.name for role in self.roles.all()])

    def get_primary_role(self):
        """Get the primary role (Group Admin > Leader > Deputy Leader > Board Member > Member)"""
        role_priority = ['Group Admin', 'Leader', 'Deputy Leader', 'Board Member', 'Member']
        for role_name in role_priority:
            if self.has_role(role_name):
                return role_name
        return 'Member'

# Register models for audit logging
auditlog.register(Group)
auditlog.register(GroupMember)
