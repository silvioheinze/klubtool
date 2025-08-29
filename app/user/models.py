from django.contrib.auth.models import AbstractUser
from django.db import models
from auditlog.registry import auditlog
from auditlog.models import AuditlogHistoryField


class Role(models.Model):
    """Role model for role-based access control"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    permissions = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_permissions(self):
        """Get list of permissions for this role"""
        return self.permissions.get('permissions', [])

    def has_permission(self, permission):
        """Check if role has specific permission"""
        return permission in self.get_permissions()


class CustomUser(AbstractUser):
    history = AuditlogHistoryField()
    
    # Add role field
    role = models.ForeignKey(
        Role, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='users'
    )
    
    # Add related_name to avoid field clashes
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='custom_user_set',
        related_query_name='custom_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='custom_user_set',
        related_query_name='custom_user',
    )

    class Meta:
        ordering = ['username']

    def __str__(self):
        return f"{self.username} ({self.email})"

    def has_role_permission(self, permission):
        """Check if user has permission through their role"""
        if self.role and self.role.is_active:
            return self.role.has_permission(permission)
        return False

    def get_all_permissions(self):
        """Get all permissions for the user (Django + role-based)"""
        permissions = set()
        
        # Django permissions
        permissions.update(self.get_group_permissions())
        permissions.update(self.get_user_permissions())
        
        # Role-based permissions
        if self.role and self.role.is_active:
            permissions.update(self.role.get_permissions())
        
        return permissions

    def has_any_permission(self, permissions):
        """Check if user has any of the given permissions"""
        user_permissions = self.get_all_permissions()
        return any(perm in user_permissions for perm in permissions)


# Register models for audit logging
auditlog.register(CustomUser)
auditlog.register(Role)