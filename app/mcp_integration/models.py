from django.db import models
from django.utils.translation import gettext_lazy as _


class McpExposedModel(models.Model):
    """Configuration for which Django models are exposed via the MCP server."""

    app_label = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    allow_query = models.BooleanField(default=False)
    allow_create = models.BooleanField(default=False)
    allow_update = models.BooleanField(default=False)
    allow_delete = models.BooleanField(default=False)
    exclude_fields = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('app_label', 'model_name')]
        ordering = ['app_label', 'model_name']
        verbose_name = _('MCP exposed model')
        verbose_name_plural = _('MCP exposed models')

    def __str__(self):
        return f'{self.app_label}.{self.model_name}'

    @property
    def is_enabled(self):
        return any([
            self.allow_query,
            self.allow_create,
            self.allow_update,
            self.allow_delete,
        ])

    @classmethod
    def get_config(cls, app_label, model_name):
        try:
            return cls.objects.get(app_label=app_label, model_name=model_name)
        except cls.DoesNotExist:
            return None
