from django.urls import path
from .views import (
    GroupListView, GroupDetailView, GroupCreateView, GroupUpdateView, GroupDeleteView,
    GroupMemberListView, GroupMemberDetailView, GroupMemberCreateView, GroupMemberUpdateView, GroupMemberDeleteView,
    group_management_view, set_group_admin, remove_group_admin, update_member_roles
)

app_name = 'group'

urlpatterns = [
    # Group Management Dashboard
    path('management/', group_management_view, name='group-management'),
    
    # Group URLs
    path('', GroupListView.as_view(), name='group-list'),
    path('create/', GroupCreateView.as_view(), name='group-create'),
    path('<int:pk>/', GroupDetailView.as_view(), name='group-detail'),
    path('<int:pk>/edit/', GroupUpdateView.as_view(), name='group-edit'),
    path('<int:pk>/delete/', GroupDeleteView.as_view(), name='group-delete'),
    
    # Group Member URLs
    path('members/', GroupMemberListView.as_view(), name='member-list'),
    path('members/create/', GroupMemberCreateView.as_view(), name='member-create'),
    path('members/<int:pk>/', GroupMemberDetailView.as_view(), name='member-detail'),
    path('members/<int:pk>/edit/', GroupMemberUpdateView.as_view(), name='member-edit'),
    path('members/<int:pk>/delete/', GroupMemberDeleteView.as_view(), name='member-delete'),
    
    # Group Admin URLs
    path('members/<int:pk>/set-admin/', set_group_admin, name='member-set-admin'),
    path('members/<int:pk>/remove-admin/', remove_group_admin, name='member-remove-admin'),
    
    # Role Management URLs
    path('members/update-roles/', update_member_roles, name='member-update-roles'),
]
