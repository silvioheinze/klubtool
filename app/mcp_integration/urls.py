from django.urls import path

from .views import McpSettingsView

app_name = 'mcp_integration'

urlpatterns = [
    path('settings/', McpSettingsView.as_view(), name='settings'),
]
