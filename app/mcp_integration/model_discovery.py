from dataclasses import dataclass

from django.apps import apps

MCP_APP_LABELS = ('user', 'local', 'group', 'motion')

NON_SELECTABLE_MODELS = {
    ('mcp_integration', 'McpExposedModel'),
    ('user', 'CalendarSubscriptionToken'),
}

SENSITIVE_MODELS = {
    ('user', 'CustomUser'),
}

MODELS_WITHOUT_DELETE = SENSITIVE_MODELS

DEFAULT_SENSITIVE_FIELDS = frozenset({
    'password',
    'last_login',
    'token_hash',
    'token',
    'secret',
})


@dataclass(frozen=True)
class DiscoverableModel:
    app_label: str
    model_name: str
    verbose_name: str
    is_sensitive: bool
    allow_delete_in_ui: bool

    @property
    def key(self):
        return f'{self.app_label}.{self.model_name}'


def is_model_selectable(app_label, model_name):
    return (app_label, model_name) not in NON_SELECTABLE_MODELS


def get_discoverable_models():
    """Return all models from project apps that superusers can expose via MCP."""
    results = []
    for app_label in MCP_APP_LABELS:
        try:
            app_config = apps.get_app_config(app_label)
        except LookupError:
            continue
        for model in app_config.get_models():
            if not is_model_selectable(app_label, model.__name__):
                continue
            is_sensitive = (app_label, model.__name__) in SENSITIVE_MODELS
            allow_delete = (app_label, model.__name__) not in MODELS_WITHOUT_DELETE
            results.append(DiscoverableModel(
                app_label=app_label,
                model_name=model.__name__,
                verbose_name=str(model._meta.verbose_name),
                is_sensitive=is_sensitive,
                allow_delete_in_ui=allow_delete,
            ))
    return sorted(results, key=lambda item: (item.app_label, item.model_name))


def get_discoverable_models_by_app():
    grouped = {}
    for model in get_discoverable_models():
        grouped.setdefault(model.app_label, []).append(model)
    return grouped


def get_model_class(app_label, model_name):
    return apps.get_model(app_label, model_name)


def get_default_exclude_fields(model):
    excluded = set()
    for field in model._meta.get_fields():
        if field.auto_created and not field.concrete:
            excluded.add(field.name)
        if field.name in DEFAULT_SENSITIVE_FIELDS:
            excluded.add(field.name)
    return sorted(excluded)
