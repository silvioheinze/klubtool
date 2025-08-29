from django.contrib.auth.models import AbstractUser
from django.db import models
from auditlog.registry import auditlog
from auditlog.models import AuditlogHistoryField


class CustomUser(AbstractUser):
    history = AuditlogHistoryField()
    
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


auditlog.register(CustomUser)