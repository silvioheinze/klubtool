import logging

from django.apps import apps
from django.db import DatabaseError, OperationalError
from django.db.models import Q
from mcp_server import ModelQueryToolset
from mcp_server.djangomcp import global_mcp_server
from mcp_server.query_tool import ModelQueryToolsetMeta
from rest_framework import serializers
from rest_framework.generics import CreateAPIView, DestroyAPIView, UpdateAPIView

from .model_discovery import get_default_exclude_fields, get_model_class
from .models import McpExposedModel

logger = logging.getLogger(__name__)

_registered_dynamic_classes = []


def _table_ready():
    if not apps.is_installed('mcp_integration'):
        return False
    try:
        McpExposedModel._meta.db_table
        from django.db import connection
        return McpExposedModel._meta.db_table in connection.introspection.table_names()
    except (DatabaseError, OperationalError):
        return False


def _clear_dynamic_registrations():
    global _registered_dynamic_classes
    for class_name in _registered_dynamic_classes:
        ModelQueryToolsetMeta.registry.pop(class_name, None)
    _registered_dynamic_classes = []


def _make_serializer(model_class, exclude_fields):
    excluded = set(exclude_fields or [])
    excluded.update(get_default_exclude_fields(model_class))

    class DynamicSerializer(serializers.ModelSerializer):
        class Meta:
            model = model_class
            fields = '__all__'
            extra_kwargs = {
                field_name: {'write_only': True}
                for field_name in excluded
                if field_name in {f.name for f in model_class._meta.get_fields()}
            }

        def get_fields(self):
            fields = super().get_fields()
            for field_name in excluded:
                fields.pop(field_name, None)
            return fields

    DynamicSerializer.__name__ = f'Mcp{model_class.__name__}Serializer'
    DynamicSerializer.__module__ = __name__
    return DynamicSerializer


def _register_query_toolset(config, model):
    exclude_fields = list(config.exclude_fields or get_default_exclude_fields(model))
    class_name = f'McpQuery_{config.app_label}_{config.model_name}'

    toolset_cls = type(
        class_name,
        (ModelQueryToolset,),
        {
            'model': model,
            'exclude_fields': exclude_fields,
            '__module__': __name__,
        },
    )
    _registered_dynamic_classes.append(class_name)
    return toolset_cls


def _register_create_tool(config, model, serializer_class):
    class_name = f'McpCreate_{config.app_label}_{config.model_name}'

    view_class = type(
        class_name,
        (CreateAPIView,),
        {
            'queryset': model.objects.all(),
            'serializer_class': serializer_class,
            '__doc__': f'Create a new {model._meta.verbose_name} record.',
            '__module__': __name__,
        },
    )
    global_mcp_server.register_drf_create_tool(
        view_class,
        name=f'create_{config.app_label}_{config.model_name.lower()}',
        instructions=f'Create a new {model._meta.verbose_name} record.',
    )
    _registered_dynamic_classes.append(class_name)


def _register_update_tool(config, model, serializer_class):
    class_name = f'McpUpdate_{config.app_label}_{config.model_name}'

    view_class = type(
        class_name,
        (UpdateAPIView,),
        {
            'queryset': model.objects.all(),
            'serializer_class': serializer_class,
            'lookup_field': 'pk',
            '__doc__': f'Update an existing {model._meta.verbose_name} record by primary key.',
            '__module__': __name__,
        },
    )
    global_mcp_server.register_drf_update_tool(
        view_class,
        name=f'update_{config.app_label}_{config.model_name.lower()}',
        instructions=f'Update an existing {model._meta.verbose_name} record by primary key.',
    )
    _registered_dynamic_classes.append(class_name)


def _register_delete_tool(config, model):
    class_name = f'McpDelete_{config.app_label}_{config.model_name}'

    view_class = type(
        class_name,
        (DestroyAPIView,),
        {
            'queryset': model.objects.all(),
            'lookup_field': 'pk',
            '__doc__': f'Delete a {model._meta.verbose_name} record by primary key.',
            '__module__': __name__,
        },
    )
    global_mcp_server.register_drf_destroy_tool(
        view_class,
        name=f'delete_{config.app_label}_{config.model_name.lower()}',
        instructions=f'Delete a {model._meta.verbose_name} record by primary key.',
    )
    _registered_dynamic_classes.append(class_name)


def register_enabled_models():
    """Register MCP tools for all enabled models. Called during app startup."""
    if not _table_ready():
        return

    _clear_dynamic_registrations()

    try:
        configs = McpExposedModel.objects.filter(
            Q(allow_query=True)
            | Q(allow_create=True)
            | Q(allow_update=True)
            | Q(allow_delete=True)
        )
    except (DatabaseError, OperationalError):
        logger.debug('MCP model registry skipped: database not ready')
        return

    for config in configs:
        try:
            model = get_model_class(config.app_label, config.model_name)
        except LookupError:
            logger.warning('Skipping unknown model %s.%s', config.app_label, config.model_name)
            continue

        exclude_fields = list(config.exclude_fields or get_default_exclude_fields(model))

        if config.allow_query:
            _register_query_toolset(config, model)

        serializer_class = None
        if config.allow_create or config.allow_update:
            serializer_class = _make_serializer(model, exclude_fields)

        if config.allow_create and serializer_class is not None:
            _register_create_tool(config, model, serializer_class)

        if config.allow_update and serializer_class is not None:
            _register_update_tool(config, model, serializer_class)

        if config.allow_delete:
            _register_delete_tool(config, model)
