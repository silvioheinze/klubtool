from django.urls import path
from .views import (
    GroupListView, GroupDetailView, GroupCreateView, GroupUpdateView, GroupDeleteView,
    GroupMemberListView, GroupMemberDetailView, GroupMemberCreateView, GroupMemberUpdateView, GroupMemberDeleteView,
    GroupMeetingListView, GroupMeetingDetailView, GroupMeetingCreateView, GroupMeetingUpdateView, GroupMeetingDeleteView,
    AgendaItemCreateView, AgendaItemDetailView, AgendaItemUpdateView, AgendaItemDeleteView,
    AgendaItemCreateAjaxView, AgendaItemUpdateOrderAjaxView,
    set_group_admin, remove_group_admin, update_member_roles
)

app_name = 'group'

urlpatterns = [
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
    
    # Group Meeting URLs
    path('meetings/', GroupMeetingListView.as_view(), name='meeting-list'),
    path('meetings/create/', GroupMeetingCreateView.as_view(), name='meeting-create'),
    path('meetings/<int:pk>/', GroupMeetingDetailView.as_view(), name='meeting-detail'),
    path('meetings/<int:pk>/edit/', GroupMeetingUpdateView.as_view(), name='meeting-edit'),
    path('meetings/<int:pk>/delete/', GroupMeetingDeleteView.as_view(), name='meeting-delete'),
    
    # Agenda Item URLs
    path('meetings/<int:meeting_id>/agenda/create/', AgendaItemCreateView.as_view(), name='agenda-item-create'),
    path('agenda/<int:pk>/', AgendaItemDetailView.as_view(), name='agenda-item-detail'),
    path('agenda/<int:pk>/edit/', AgendaItemUpdateView.as_view(), name='agenda-item-edit'),
    path('agenda/<int:pk>/delete/', AgendaItemDeleteView.as_view(), name='agenda-item-delete'),
    
    # AJAX Agenda URLs
    path('meetings/<int:meeting_id>/agenda/create-ajax/', AgendaItemCreateAjaxView.as_view(), name='agenda-item-create-ajax'),
    path('meetings/<int:meeting_id>/agenda/update-order/', AgendaItemUpdateOrderAjaxView.as_view(), name='agenda-item-update-order'),
    
    # Group Admin URLs
    path('members/<int:pk>/set-admin/', set_group_admin, name='member-set-admin'),
    path('members/<int:pk>/remove-admin/', remove_group_admin, name='member-remove-admin'),
    
    # Role Management URLs
    path('members/update-roles/', update_member_roles, name='member-update-roles'),
]
