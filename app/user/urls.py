from django.urls import path, include
from django.shortcuts import redirect

from user.views import (
    AccountDeleteView, SettingsView, SignupPageView,
    UsersUpdateView, UsersListView, RoleListView, RoleCreateView,
    RoleUpdateView, RoleDeleteView, AdminUserCreateView, AdminSettingsView,
    send_welcome_email, CustomConfirmEmailView, calendar_subscription_create,
)


def redirect_password_change(request):
    """Redirect /user/edit/password/ to the correct Allauth password change URL"""
    return redirect('account_change_password')

urlpatterns = [
    # User Management
    path('delete/', AccountDeleteView.as_view(), name='user-delete'),
    path('settings/', SettingsView, name='user-settings'),
    path('settings/calendar-subscription/create/', calendar_subscription_create, name='calendar-subscription-create'),
    path("signup/", SignupPageView.as_view(), name="user-signup"),
    path('list/', UsersListView.as_view(), name='user-list'),
    path('edit/<int:user_id>/', UsersUpdateView.as_view(), name='user-edit'),
    path('edit/password/', redirect_password_change, name='user-password-change-redirect'),
    path('send-welcome-email/<int:user_id>/', send_welcome_email, name='user-send-welcome-email'),
    
    # Role Management
    path('roles/', RoleListView.as_view(), name='role-list'),
    path('roles/create/', RoleCreateView.as_view(), name='role-create'),
    path('roles/<int:pk>/edit/', RoleUpdateView.as_view(), name='role-edit'),
    path('roles/<int:pk>/delete/', RoleDeleteView.as_view(), name='role-delete'),
    
    # User Management Dashboard
    path('admin-create/', AdminUserCreateView.as_view(), name='admin-user-create'),
    
    # Admin Settings
    path('admin-settings/', AdminSettingsView.as_view(), name='admin-settings'),
    
    # Custom email confirmation view (override allauth's default - must come before include)
    path('confirm-email/<str:key>/', CustomConfirmEmailView.as_view(), name='account_confirm_email'),
    
    # Allauth URLs
    path("", include("allauth.account.urls")),
]