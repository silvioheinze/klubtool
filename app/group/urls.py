from django.urls import path
from .views import (
    GroupListView, GroupDetailView, GroupCreateView, GroupUpdateView, GroupDeleteView,
    GroupMemberDetailView, GroupMemberCreateView, GroupMemberUpdateView, GroupMemberDeleteView,
    GroupMeetingListView, GroupMeetingDetailView, GroupMeetingCreateView, GroupMeetingUpdateView, GroupMeetingDeleteView, GroupMeetingCancelView, GroupMeetingAgendaExportPDFView, GroupMeetingMinutesExportPDFView,
    AgendaItemCreateView, AgendaItemDetailView, AgendaItemUpdateView, AgendaItemDeleteView,
    AgendaItemCreateAjaxView, AgendaItemUpdateAjaxView, AgendaItemUpdateOrderAjaxView,
    MinuteItemCreateAjaxView, MinuteItemUpdateAjaxView, MinuteItemDeleteView,
    set_group_admin, remove_group_admin, update_member_roles, send_meeting_invites, meeting_export_ics,
    invite_member,
)

app_name = 'group'

urlpatterns = [
    # Group URLs
    path('', GroupListView.as_view(), name='group-list'),
    path('create/', GroupCreateView.as_view(), name='group-create'),
    path('<int:pk>/', GroupDetailView.as_view(), name='group-detail'),
    path('<int:pk>/edit/', GroupUpdateView.as_view(), name='group-edit'),
    path('<int:pk>/delete/', GroupDeleteView.as_view(), name='group-delete'),
    path('<int:pk>/invite-member/', invite_member, name='group-invite-member'),
    
    # Group Member URLs
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
    path('meetings/<int:pk>/cancel/', GroupMeetingCancelView.as_view(), name='meeting-cancel'),
    path('meetings/<int:pk>/send-invites/', send_meeting_invites, name='meeting-send-invites'),
    path('meetings/<int:pk>/export-ics/', meeting_export_ics, name='meeting-export-ics'),
    path('meetings/<int:pk>/export-agenda-pdf/', GroupMeetingAgendaExportPDFView.as_view(), name='meeting-export-agenda-pdf'),
    path('meetings/<int:pk>/export-minutes-pdf/', GroupMeetingMinutesExportPDFView.as_view(), name='meeting-export-minutes-pdf'),
    
    # Agenda Item URLs
    path('meetings/<int:meeting_id>/agenda/create/', AgendaItemCreateView.as_view(), name='agenda-item-create'),
    path('agenda/<int:pk>/', AgendaItemDetailView.as_view(), name='agenda-item-detail'),
    path('agenda/<int:pk>/edit/', AgendaItemUpdateView.as_view(), name='agenda-item-edit'),
    path('agenda/<int:pk>/delete/', AgendaItemDeleteView.as_view(), name='agenda-item-delete'),
    
    # AJAX Agenda URLs
    path('meetings/<int:meeting_id>/agenda/create-ajax/', AgendaItemCreateAjaxView.as_view(), name='agenda-item-create-ajax'),
    path('agenda/<int:agenda_item_id>/update-ajax/', AgendaItemUpdateAjaxView.as_view(), name='agenda-item-update-ajax'),
    path('meetings/<int:meeting_id>/agenda/update-order/', AgendaItemUpdateOrderAjaxView.as_view(), name='agenda-item-update-order'),
    
    # Minute item URLs (when meeting status is invited)
    path('meetings/<int:meeting_id>/minutes/create-ajax/', MinuteItemCreateAjaxView.as_view(), name='minute-item-create-ajax'),
    path('minutes/<int:minute_item_id>/update-ajax/', MinuteItemUpdateAjaxView.as_view(), name='minute-item-update-ajax'),
    path('minutes/<int:pk>/delete/', MinuteItemDeleteView.as_view(), name='minute-item-delete'),
    
    # Group Admin URLs
    path('members/<int:pk>/set-admin/', set_group_admin, name='member-set-admin'),
    path('members/<int:pk>/remove-admin/', remove_group_admin, name='member-remove-admin'),
    
    # Role Management URLs
    path('members/update-roles/', update_member_roles, name='member-update-roles'),
]
