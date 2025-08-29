from django.urls import path, include

#from .views import SignupPageView
from user.views import AccountDeleteView, DashboardView, SettingsView, SignupPageView, UsersUpdateView, UsersListView


urlpatterns = [
    path('dashboard/', DashboardView, name='user-dashboard'),
    path('delete/', AccountDeleteView.as_view(), name='user-delete'),
    path('settings/', SettingsView, name='user-settings'),
    path("signup/", SignupPageView.as_view(), name="user-signup"),
    path('list/', UsersListView.as_view(), name='user-list'),
    path('edit/<int:user_id>/', UsersUpdateView.as_view(), name='user-edit'),
    path("", include("allauth.account.urls")),
]