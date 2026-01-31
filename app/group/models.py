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
    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name='groups', help_text="Party this group belongs to")
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
        """Check if a user can manage this group (superuser, group admin, leader, or deputy leader)"""
        if user.is_superuser:
            return True
        
        # Check if user is a group admin
        if self.has_group_admin(user):
            return True
        
        # Check if user is a leader or deputy leader of this group
        return GroupMember.objects.filter(
            user=user,
            group=self,
            is_active=True,
            roles__name__in=['Leader', 'Deputy Leader']
        ).exists()




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
        ordering = ['-joined_date', '-id']
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


class GroupMeeting(models.Model):
    """Model representing a meeting of a political group"""
    
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='meetings', help_text="Group holding the meeting")
    title = models.CharField(max_length=200, help_text="Title or name of the meeting")
    scheduled_date = models.DateTimeField(help_text="Date and time when the meeting is scheduled")
    location = models.CharField(max_length=300, blank=True, help_text="Location where the meeting will be held")
    description = models.TextField(blank=True, help_text="Description or agenda of the meeting")
    is_active = models.BooleanField(default=True, help_text="Whether the meeting is currently active")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_meetings', help_text="User who created the meeting")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-scheduled_date']
        verbose_name = "Group Meeting"
        verbose_name_plural = "Group Meetings"

    def __str__(self):
        return f"{self.title} - {self.group.name} ({self.scheduled_date.strftime('%Y-%m-%d %H:%M')})"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('group:meeting-detail', args=[str(self.pk)])

    @property
    def is_past(self):
        """Check if the meeting is in the past"""
        return self.scheduled_date < timezone.now()

    @property
    def is_upcoming(self):
        """Check if the meeting is upcoming"""
        return self.scheduled_date > timezone.now()

    @property
    def time_until_meeting(self):
        """Get time until the meeting"""
        now = timezone.now()
        if self.scheduled_date > now:
            delta = self.scheduled_date - now
            if delta.days > 0:
                return f"{delta.days} days"
            elif delta.seconds > 3600:
                hours = delta.seconds // 3600
                return f"{hours} hours"
            else:
                minutes = delta.seconds // 60
                return f"{minutes} minutes"
        return "Past"


class AgendaItem(models.Model):
    """Model representing an agenda item for a group meeting"""
    
    meeting = models.ForeignKey(GroupMeeting, on_delete=models.CASCADE, related_name='agenda_items', help_text="Meeting this agenda item belongs to")
    title = models.CharField(max_length=200, help_text="Title of the agenda item")
    description = models.TextField(blank=True, help_text="Description or details of the agenda item")
    parent_item = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='sub_items', help_text="Parent agenda item if this is a sub-item")
    order = models.PositiveIntegerField(default=0, help_text="Order of the agenda item within the meeting")
    is_active = models.BooleanField(default=True, help_text="Whether the agenda item is currently active")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_agenda_items', help_text="User who created the agenda item")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = "Agenda Item"
        verbose_name_plural = "Agenda Items"

    def __str__(self):
        return f"{self.title} - {self.meeting.title}"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('group:agenda-item-detail', args=[str(self.pk)])

    @property
    def is_sub_item(self):
        """Check if this is a sub-item (has a parent)"""
        return self.parent_item is not None

    @property
    def level(self):
        """Get the nesting level of this agenda item"""
        level = 0
        current = self.parent_item
        while current:
            level += 1
            current = current.parent_item
        return level

    def get_sub_items(self):
        """Get all sub-items of this agenda item"""
        return self.sub_items.filter(is_active=True).order_by('order')

    def get_siblings(self):
        """Get all sibling agenda items (same parent)"""
        if self.parent_item:
            return self.parent_item.get_sub_items().exclude(pk=self.pk)
        else:
            return self.meeting.agenda_items.filter(parent_item__isnull=True, is_active=True).exclude(pk=self.pk).order_by('order')

# Register models for audit logging
auditlog.register(Group)
auditlog.register(GroupMember)
auditlog.register(GroupMeeting)
auditlog.register(AgendaItem)
