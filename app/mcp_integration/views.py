from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from rest_framework.authtoken.models import Token

from .model_discovery import get_discoverable_models_by_app
from .models import McpExposedModel


class McpSettingsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'mcp_integration/settings.html'

    def test_func(self):
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        configs = {
            (item.app_label, item.model_name): item
            for item in McpExposedModel.objects.all()
        }
        model_rows = []
        for app_label, models in get_discoverable_models_by_app().items():
            rows = []
            for model in models:
                config = configs.get((model.app_label, model.model_name))
                rows.append({
                    'model': model,
                    'allow_query': config.allow_query if config else False,
                    'allow_create': config.allow_create if config else False,
                    'allow_update': config.allow_update if config else False,
                    'allow_delete': config.allow_delete if config else False,
                })
            model_rows.append({'app_label': app_label, 'rows': rows})

        token = Token.objects.filter(user=self.request.user).first()
        context.update({
            'model_groups': model_rows,
            'has_token': token is not None,
            'mcp_endpoint': self.request.build_absolute_uri('/mcp'),
            'new_token': self.request.session.pop('mcp_new_token', None),
        })
        return context

    def post(self, request, *args, **kwargs):
        if 'create_token' in request.POST:
            Token.objects.filter(user=request.user).delete()
            token = Token.objects.create(user=request.user)
            request.session['mcp_new_token'] = token.key
            messages.success(
                request,
                _('API token created. Copy it now — it will not be shown again.'),
            )
            return redirect('mcp_integration:settings')

        if 'revoke_token' in request.POST:
            Token.objects.filter(user=request.user).delete()
            messages.success(request, _('API token revoked.'))
            return redirect('mcp_integration:settings')

        if 'save_models' in request.POST:
            self._save_model_config(request)
            messages.success(
                request,
                _(
                    'MCP model settings saved. Restart the server or run '
                    '"python manage.py reload_mcp_models" for changes to take effect.'
                ),
            )
            return redirect('mcp_integration:settings')

        return redirect('mcp_integration:settings')

    def _save_model_config(self, request):
        submitted_keys = set()

        for app_label, models in get_discoverable_models_by_app().items():
            for model in models:
                key = f'{model.app_label}.{model.model_name}'
                submitted_keys.add(key)

                allow_query = request.POST.get(f'query_{key}') == 'on'
                allow_create = request.POST.get(f'create_{key}') == 'on'
                allow_update = request.POST.get(f'update_{key}') == 'on'
                allow_delete = request.POST.get(f'delete_{key}') == 'on'

                if model.is_sensitive:
                    allow_create = False
                    allow_update = False
                    allow_delete = False

                if not model.allow_delete_in_ui:
                    allow_delete = False

                if any([allow_query, allow_create, allow_update, allow_delete]):
                    McpExposedModel.objects.update_or_create(
                        app_label=model.app_label,
                        model_name=model.model_name,
                        defaults={
                            'allow_query': allow_query,
                            'allow_create': allow_create,
                            'allow_update': allow_update,
                            'allow_delete': allow_delete,
                        },
                    )
                else:
                    McpExposedModel.objects.filter(
                        app_label=model.app_label,
                        model_name=model.model_name,
                    ).delete()
