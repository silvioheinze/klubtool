from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
from django.http import HttpResponse
from django.utils import timezone
from .models import Group, GroupMember, GroupMeeting, AgendaItem
from .forms import GroupForm, GroupFilterForm, GroupMemberForm, GroupMemberFilterForm, GroupMeetingForm, AgendaItemForm, GroupInviteForm

User = get_user_model()

def is_superuser_or_has_permission(permission):
    """Decorator to check if user is superuser or has specific permission"""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if request.user.is_superuser or request.user.has_role_permission(permission):
                return view_func(request, *args, **kwargs)
            messages.error(request, "You don't have permission to access this page.")
            return redirect('home')
        return wrapper
    return decorator

# Group Views
class GroupListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Group
    template_name = 'group/group_list.html'
    context_object_name = 'groups'
    paginate_by = 20

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_role_permission('group.view')

    def get_queryset(self):
        queryset = Group.objects.select_related('party', 'party__local').all()
        
        # Apply filters
        form = GroupFilterForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data.get('name'):
                queryset = queryset.filter(name__icontains=form.cleaned_data['name'])
            if form.cleaned_data.get('party'):
                queryset = queryset.filter(party=form.cleaned_data['party'])
            if form.cleaned_data.get('is_active') in ['True', 'False']:
                queryset = queryset.filter(is_active=form.cleaned_data['is_active'] == 'True')
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = GroupFilterForm(self.request.GET)
        return context

class GroupDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Group
    template_name = 'group/group_detail.html'
    context_object_name = 'group'

    def test_func(self):
        # Allow superusers, users with group.view permission, or group admins
        if self.request.user.is_superuser or self.request.user.has_role_permission('group.view'):
            return True
        # Check if user is a group admin of this specific group
        group = self.get_object()
        return group.can_user_manage_group(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['members'] = self.object.members.select_related('user').filter(is_active=True).order_by('user__first_name', 'user__last_name', 'user__username')
        context['active_members'] = context['members'].filter(is_active=True)
        
        # Add meetings data
        context['meetings'] = self.object.meetings.filter(is_active=True).order_by('-scheduled_date')[:6]
        context['total_meetings'] = self.object.meetings.filter(is_active=True).count()
        
        # Add available roles for role management
        from user.models import Role
        context['available_roles'] = Role.objects.filter(is_active=True).order_by('name')
        
        return context

class GroupCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Group
    form_class = GroupForm
    template_name = 'group/group_form.html'
    success_url = reverse_lazy('group:group-list')

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_role_permission('group.create')

    def form_valid(self, form):
        messages.success(self.request, f"Group '{form.instance.name}' created successfully.")
        return super().form_valid(form)

class GroupUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Group
    form_class = GroupForm
    template_name = 'group/group_form.html'
    success_url = reverse_lazy('group:group-list')

    def test_func(self):
        # Allow superusers, users with group.edit permission, or group admins
        if self.request.user.is_superuser or self.request.user.has_role_permission('group.edit'):
            return True
        # Check if user is a group admin of this specific group
        group = self.get_object()
        return group.can_user_manage_group(self.request.user)

    def form_valid(self, form):
        messages.success(self.request, f"Group '{form.instance.name}' updated successfully.")
        return super().form_valid(form)

class GroupDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Group
    template_name = 'group/group_confirm_delete.html'
    success_url = reverse_lazy('group:group-list')

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_role_permission('group.delete')

    def delete(self, request, *args, **kwargs):
        group_name = self.get_object().name
        messages.success(request, f"Group '{group_name}' deleted successfully.")
        return super().delete(request, *args, **kwargs)

# Group Member Views
class GroupMemberListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = GroupMember
    template_name = 'group/member_list.html'
    context_object_name = 'members'
    paginate_by = 20

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_role_permission('group.view')

    def get_queryset(self):
        queryset = GroupMember.objects.select_related('user', 'group', 'group__party').all()
        
        # Apply filters
        form = GroupMemberFilterForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data.get('user'):
                queryset = queryset.filter(user=form.cleaned_data['user'])
            if form.cleaned_data.get('group'):
                queryset = queryset.filter(group=form.cleaned_data['group'])
            if form.cleaned_data.get('role'):
                queryset = queryset.filter(roles=form.cleaned_data['role'])
            if form.cleaned_data.get('is_active') in ['True', 'False']:
                queryset = queryset.filter(is_active=form.cleaned_data['is_active'] == 'True')
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = GroupMemberFilterForm(self.request.GET)
        return context

class GroupMemberDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = GroupMember
    template_name = 'group/member_detail.html'
    context_object_name = 'member'

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_role_permission('group.view')

class GroupMemberCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = GroupMember
    form_class = GroupMemberForm
    template_name = 'group/member_form.html'

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_role_permission('group.create')

    def get_initial(self):
        """Set initial values for the form"""
        initial = super().get_initial()
        group_id = self.request.GET.get('group')
        if group_id:
            initial['group'] = group_id
        return initial

    def get_context_data(self, **kwargs):
        """Add context data for the template"""
        context = super().get_context_data(**kwargs)
        group_id = self.request.GET.get('group')
        if group_id:
            try:
                from .models import Group
                context['selected_group'] = Group.objects.get(pk=group_id)
            except Group.DoesNotExist:
                pass
        return context

    def get_success_url(self):
        """Redirect to the group detail page after successful creation"""
        if hasattr(self.object, 'group') and self.object.group:
            return reverse('group:group-detail', kwargs={'pk': self.object.group.pk})
        return reverse('group:member-list')

    def form_valid(self, form):
        messages.success(self.request, f"Member '{form.instance.user.username}' added to group '{form.instance.group.name}' successfully.")
        return super().form_valid(form)

class GroupMemberUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = GroupMember
    form_class = GroupMemberForm
    template_name = 'group/member_form.html'
    success_url = reverse_lazy('group:member-list')

    def test_func(self):
        # Allow superusers, users with group.edit permission, or group admins
        if self.request.user.is_superuser or self.request.user.has_role_permission('group.edit'):
            return True
        # Check if user is a group admin of the member's group
        member = self.get_object()
        return member.group.can_user_manage_group(self.request.user)

    def get_success_url(self):
        """Redirect to the group detail page after successful update"""
        if hasattr(self.object, 'group') and self.object.group:
            return reverse('group:group-detail', kwargs={'pk': self.object.group.pk})
        return reverse('group:member-list')

    def form_valid(self, form):
        messages.success(self.request, f"Membership updated successfully.")
        return super().form_valid(form)

class GroupMemberDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = GroupMember
    template_name = 'group/member_confirm_delete.html'
    success_url = reverse_lazy('group:member-list')

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_role_permission('group.delete')

    def delete(self, request, *args, **kwargs):
        member = self.get_object()
        messages.success(request, f"Member '{member.user.username}' removed from group '{member.group.name}' successfully.")
        return super().delete(request, *args, **kwargs)


@login_required
def set_group_admin(request, pk):
    """Set a group member as group admin"""
    member = get_object_or_404(GroupMember, pk=pk)
    
    # Check permissions
    if not (request.user.is_superuser or member.group.can_user_manage_group(request.user)):
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('group:group-detail', pk=member.group.pk)
    
    # Get or create admin role
    from user.models import Role
    admin_role, created = Role.objects.get_or_create(
        name='Group Admin',
        defaults={'description': 'Group administration role', 'is_active': True}
    )
    
    # Add admin role if not already present
    if not member.roles.filter(name='Group Admin').exists():
        member.roles.add(admin_role)
        messages.success(request, f"'{member.user.username}' is now a Group Admin of '{member.group.name}'.")
    else:
        messages.info(request, f"'{member.user.username}' is already a Group Admin of '{member.group.name}'.")
    
    return redirect('group:group-detail', pk=member.group.pk)


@login_required
def remove_group_admin(request, pk):
    """Remove group admin role from a group member"""
    member = get_object_or_404(GroupMember, pk=pk)
    
    # Check permissions
    if not (request.user.is_superuser or member.group.can_user_manage_group(request.user)):
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('group:group-detail', pk=member.group.pk)
    
    # Remove admin role
    admin_role = member.roles.filter(name='Group Admin').first()
    if admin_role:
        member.roles.remove(admin_role)
        messages.success(request, f"'{member.user.username}' is no longer a Group Admin of '{member.group.name}'.")
    else:
        messages.info(request, f"'{member.user.username}' is not a Group Admin of '{member.group.name}'.")
    
    return redirect('group:group-detail', pk=member.group.pk)

# Additional Views


@login_required
def update_member_roles(request):
    """Update member roles via AJAX/form submission"""
    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return redirect('group:group-list')
    
    member_id = request.POST.get('member_id')
    selected_roles = request.POST.getlist('roles')
    
    try:
        member = GroupMember.objects.get(pk=member_id)
    except GroupMember.DoesNotExist:
        messages.error(request, "Member not found.")
        return redirect('group:group-list')
    
    # Check permissions
    if not (request.user.is_superuser or member.group.can_user_manage_group(request.user)):
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('group:group-detail', pk=member.group.pk)
    
    # Get selected roles
    from user.models import Role
    roles_to_assign = Role.objects.filter(id__in=selected_roles, is_active=True)
    
    # Update member roles
    member.roles.clear()
    member.roles.add(*roles_to_assign)
    
    # Ensure member has at least the basic Member role if no roles selected
    if not roles_to_assign.exists():
        member_role, created = Role.objects.get_or_create(
            name='Member',
            defaults={'description': 'Basic group membership role', 'is_active': True}
        )
        member.roles.add(member_role)
    
    messages.success(request, f"Roles updated for '{member.user.username}' successfully.")
    return redirect('group:group-detail', pk=member.group.pk)


# Group Meeting Views
class GroupMeetingListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View for listing all GroupMeeting objects"""
    model = GroupMeeting
    context_object_name = 'meetings'
    template_name = 'group/meeting_list.html'
    paginate_by = 20

    def test_func(self):
        """Check if user has permission to view GroupMeeting objects"""
        return self.request.user.is_superuser

    def get_queryset(self):
        """Filter queryset based on search parameters"""
        queryset = GroupMeeting.objects.all().select_related('group', 'created_by').order_by('-scheduled_date')
        
        # Filter by search query
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(group__name__icontains=search_query) |
                Q(location__icontains=search_query)
            )
        
        # Filter by meeting type
        meeting_type_filter = self.request.GET.get('meeting_type', '')
        if meeting_type_filter:
            queryset = queryset.filter(meeting_type=meeting_type_filter)
        
        # Filter by group
        group_filter = self.request.GET.get('group', '')
        if group_filter:
            queryset = queryset.filter(group_id=group_filter)
        
        return queryset

    def get_context_data(self, **kwargs):
        """Add filter form to context"""
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['meeting_type_filter'] = self.request.GET.get('meeting_type', '')
        context['group_filter'] = self.request.GET.get('group', '')
        context['groups'] = Group.objects.filter(is_active=True)
        return context


class GroupMeetingDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for displaying a single GroupMeeting object"""
    model = GroupMeeting
    context_object_name = 'meeting'
    template_name = 'group/meeting_detail.html'

    def test_func(self):
        """Check if user has permission to view GroupMeeting objects"""
        if self.request.user.is_superuser:
            return True
        # Check if user can manage the meeting's group
        meeting = self.get_object()
        return meeting.group.can_user_manage_group(self.request.user)

    def get_context_data(self, **kwargs):
        """Add agenda items to context"""
        context = super().get_context_data(**kwargs)
        context['agenda_items'] = self.object.agenda_items.filter(is_active=True).order_by('order')
        
        # Check if user can manage the meeting's group
        user = self.request.user
        meeting_group = self.object.group
        can_manage = meeting_group.can_user_manage_group(user)
        context['can_view_meeting_details'] = can_manage
        context['can_send_invites'] = can_manage
        return context


@login_required
def meeting_export_ics(request, pk):
    """View to export a group meeting as an ICS calendar file"""
    meeting = get_object_or_404(GroupMeeting, pk=pk)
    # Allow: superuser, group admin/leader, or any active member of the group (e.g. from personal calendar)
    is_member = GroupMember.objects.filter(
        user=request.user, group=meeting.group, is_active=True
    ).exists()
    if not (request.user.is_superuser or meeting.group.can_user_manage_group(request.user) or is_member):
        messages.error(request, "You don't have permission to access this page.")
        return redirect('group:meeting-detail', pk=pk)
    
    # Convert scheduled_date to UTC for ICS format
    dtstart = meeting.scheduled_date
    if not timezone.is_aware(dtstart):
        dtstart = timezone.make_aware(dtstart)
    dtstart_utc = dtstart.astimezone(timezone.UTC)
    
    # Assume 1 hour duration if not specified
    dtend_utc = dtstart_utc + timezone.timedelta(hours=1)
    
    # Format dates for ICS (YYYYMMDDTHHMMSSZ)
    dtstart_str = dtstart_utc.strftime('%Y%m%dT%H%M%SZ')
    dtend_str = dtend_utc.strftime('%Y%m%dT%H%M%SZ')
    
    # Generate unique ID for the event
    uid = f"meeting-{meeting.pk}@{request.get_host()}"
    
    # Escape special characters in text fields for ICS format
    def escape_ics_text(text):
        if not text:
            return ""
        text = str(text)
        # Replace newlines with \n and escape special characters
        text = text.replace('\\', '\\\\')
        text = text.replace(',', '\\,')
        text = text.replace(';', '\\;')
        text = text.replace('\n', '\\n')
        return text
    
    # Build ICS content
    ics_content = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Klubtool//Group Meeting//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTART:{dtstart_str}",
        f"DTEND:{dtend_str}",
        f"SUMMARY:{escape_ics_text(meeting.title)}",
    ]
    
    if meeting.description:
        ics_content.append(f"DESCRIPTION:{escape_ics_text(meeting.description)}")
    
    if meeting.location:
        ics_content.append(f"LOCATION:{escape_ics_text(meeting.location)}")
    
    # Add created and last modified timestamps
    created = meeting.created_at
    if not timezone.is_aware(created):
        created = timezone.make_aware(created)
    created_utc = created.astimezone(timezone.UTC)
    ics_content.append(f"DTSTAMP:{created_utc.strftime('%Y%m%dT%H%M%SZ')}")
    
    updated = meeting.updated_at
    if not timezone.is_aware(updated):
        updated = timezone.make_aware(updated)
    updated_utc = updated.astimezone(timezone.UTC)
    ics_content.append(f"LAST-MODIFIED:{updated_utc.strftime('%Y%m%dT%H%M%SZ')}")
    
    # Add URL to the meeting detail page
    meeting_url = request.build_absolute_uri(reverse('group:meeting-detail', args=[meeting.pk]))
    ics_content.append(f"URL:{meeting_url}")
    
    ics_content.extend([
        "STATUS:CONFIRMED",
        "SEQUENCE:0",
        "END:VEVENT",
        "END:VCALENDAR"
    ])
    
    # Join lines with \r\n (ICS standard requires CRLF)
    ics_file = "\r\n".join(ics_content)
    
    # Create response
    response = HttpResponse(ics_file, content_type='text/calendar; charset=utf-8')
    filename = f"meeting_{meeting.pk}_{meeting.title.replace(' ', '_')}.ics"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


class GroupMeetingCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating a new GroupMeeting object"""
    model = GroupMeeting
    form_class = GroupMeetingForm
    template_name = 'group/meeting_form.html'

    def test_func(self):
        """Check if user has permission to create GroupMeeting objects"""
        if self.request.user.is_superuser:
            return True
        # Check if user can manage the group (if specified in URL)
        group_id = self.request.GET.get('group')
        if group_id:
            try:
                group = Group.objects.get(pk=group_id)
                return group.can_user_manage_group(self.request.user)
            except Group.DoesNotExist:
                pass
        return False

    def get_initial(self):
        """Set initial values for the form"""
        initial = super().get_initial()
        group_id = self.request.GET.get('group')
        if group_id:
            initial['group'] = group_id
        return initial

    def get_context_data(self, **kwargs):
        """Add context data for the template"""
        context = super().get_context_data(**kwargs)
        group_id = self.request.GET.get('group')
        if group_id:
            try:
                context['selected_group'] = Group.objects.get(pk=group_id)
            except Group.DoesNotExist:
                pass
        return context

    def form_valid(self, form):
        """Set the created_by field and group field, then display success message"""
        form.instance.created_by = self.request.user
        
        # Ensure group is set from URL parameter if not already set
        group_id = self.request.GET.get('group')
        if group_id and not form.instance.group_id:
            try:
                from .models import Group
                form.instance.group = Group.objects.get(pk=group_id)
            except Group.DoesNotExist:
                pass
        
        messages.success(self.request, f"Meeting '{form.instance.title}' created successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        """Redirect to the group detail page after successful creation"""
        return reverse('group:group-detail', kwargs={'pk': self.object.group.pk})


class GroupMeetingUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for updating an existing GroupMeeting object"""
    model = GroupMeeting
    form_class = GroupMeetingForm
    template_name = 'group/meeting_form.html'

    def test_func(self):
        """Check if user has permission to edit GroupMeeting objects"""
        if self.request.user.is_superuser:
            return True
        # Check if user can manage the meeting's group
        meeting = self.get_object()
        return meeting.group.can_user_manage_group(self.request.user)

    def get_success_url(self):
        """Redirect to the group detail page after successful update"""
        return reverse('group:group-detail', kwargs={'pk': self.object.group.pk})

    def form_valid(self, form):
        """Display success message on form validation"""
        messages.success(self.request, f"Meeting '{form.instance.title}' updated successfully.")
        return super().form_valid(form)


class GroupMeetingDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting a GroupMeeting object"""
    model = GroupMeeting
    template_name = 'group/meeting_confirm_delete.html'

    def test_func(self):
        """Check if user has permission to delete GroupMeeting objects"""
        if self.request.user.is_superuser:
            return True
        # Check if user can manage the meeting's group
        meeting = self.get_object()
        return meeting.group.can_user_manage_group(self.request.user)

    def get_success_url(self):
        """Redirect to the group detail page after successful deletion"""
        return reverse('group:group-detail', kwargs={'pk': self.object.group.pk})

    def delete(self, request, *args, **kwargs):
        """Display success message on deletion"""
        meeting_obj = self.get_object()
        messages.success(request, f"Meeting '{meeting_obj.title}' deleted successfully.")
        return super().delete(request, *args, **kwargs)


class GroupMeetingCancelView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View to confirm and cancel a meeting (set status to cancelled)."""
    model = GroupMeeting
    context_object_name = 'meeting'
    template_name = 'group/meeting_cancel_confirm.html'

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        meeting = self.get_object()
        return meeting.group.can_user_manage_group(self.request.user)

    def dispatch(self, request, *args, **kwargs):
        meeting = self.get_object()
        if meeting.status not in ('scheduled', 'invited'):
            messages.error(request, _("Only scheduled or invited meetings can be cancelled."))
            return redirect('group:meeting-detail', pk=meeting.pk)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        meeting = self.get_object()
        meeting.status = 'cancelled'
        meeting.save(update_fields=['status'])
        messages.success(request, _("Meeting has been cancelled."))
        return redirect('group:meeting-detail', pk=meeting.pk)


# Agenda Item Views
class AgendaItemDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for displaying a single AgendaItem object"""
    model = AgendaItem
    context_object_name = 'agenda_item'
    template_name = 'group/agenda_item_detail.html'

    def test_func(self):
        """Check if user has permission to view AgendaItem objects"""
        return self.request.user.is_superuser


class AgendaItemCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating a new AgendaItem"""
    model = AgendaItem
    form_class = AgendaItemForm
    template_name = 'group/agenda_item_form.html'

    def test_func(self):
        """Check if user has permission to create agenda items"""
        return self.request.user.is_superuser

    def get_form_kwargs(self):
        """Pass meeting to form"""
        kwargs = super().get_form_kwargs()
        meeting_id = self.kwargs.get('meeting_id')
        if meeting_id:
            from .models import GroupMeeting
            kwargs['meeting'] = GroupMeeting.objects.get(pk=meeting_id)
        return kwargs

    def form_valid(self, form):
        """Set the meeting and created_by fields"""
        meeting_id = self.kwargs.get('meeting_id')
        if meeting_id:
            from .models import GroupMeeting
            form.instance.meeting = GroupMeeting.objects.get(pk=meeting_id)
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        """Redirect to the meeting detail page"""
        return reverse('group:meeting-detail', kwargs={'pk': self.object.meeting.pk})


class AgendaItemUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for updating an existing AgendaItem"""
    model = AgendaItem
    form_class = AgendaItemForm
    template_name = 'group/agenda_item_form.html'

    def test_func(self):
        """Check if user has permission to edit agenda items"""
        return self.request.user.is_superuser

    def get_form_kwargs(self):
        """Pass meeting to form"""
        kwargs = super().get_form_kwargs()
        kwargs['meeting'] = self.object.meeting
        return kwargs

    def get_success_url(self):
        """Redirect to the meeting detail page"""
        return reverse('group:meeting-detail', kwargs={'pk': self.object.meeting.pk})


class AgendaItemDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting an AgendaItem"""
    model = AgendaItem
    template_name = 'group/agenda_item_confirm_delete.html'

    def test_func(self):
        """Check if user has permission to delete agenda items"""
        return self.request.user.is_superuser

    def get_success_url(self):
        """Redirect to the meeting detail page"""
        return reverse('group:meeting-detail', kwargs={'pk': self.object.meeting.pk})


# AJAX Views for agenda management
class AgendaItemCreateAjaxView(LoginRequiredMixin, UserPassesTestMixin, View):
    """AJAX view for creating agenda items"""
    
    def test_func(self):
        """Check if user has permission to create agenda items"""
        return self.request.user.is_superuser

    def post(self, request, meeting_id):
        """Create a new agenda item via AJAX"""
        from .models import GroupMeeting
        from django.http import JsonResponse
        import traceback
        import logging
        
        logger = logging.getLogger(__name__)
        
        try:
            # Debug: Log the request data
            logger.debug(f"AJAX request data: {request.POST}")
            logger.debug(f"Meeting ID: {meeting_id}")
            logger.debug(f"User: {request.user}")
            
            meeting = GroupMeeting.objects.get(pk=meeting_id)
            logger.debug(f"Meeting found: {meeting}")
            
            form = AgendaItemForm(request.POST, meeting=meeting)
            logger.debug(f"Form data: {request.POST}")
            logger.debug(f"Form is valid: {form.is_valid()}")
            
            if not form.is_valid():
                logger.debug(f"Form errors: {form.errors}")
                return JsonResponse({
                    'success': False,
                    'error': 'Form validation failed',
                    'errors': form.errors,
                    'debug': {
                        'form_data': dict(request.POST),
                        'form_errors': form.errors
                    }
                })
            
            agenda_item = form.save(commit=False)
            agenda_item.meeting = meeting
            agenda_item.created_by = request.user
            agenda_item.save()
            
            logger.debug(f"Agenda item created: {agenda_item}")
            
            return JsonResponse({
                'success': True,
                'message': 'Agenda item created successfully.',
                'agenda_item': {
                    'id': agenda_item.pk,
                    'title': agenda_item.title,
                    'description': agenda_item.description,
                    'order': agenda_item.order,
                    'parent_item': agenda_item.parent_item.pk if agenda_item.parent_item else None,
                    'level': agenda_item.level,
                }
            })
            
        except GroupMeeting.DoesNotExist:
            logger.error(f"Meeting with ID {meeting_id} not found")
            return JsonResponse({
                'success': False,
                'error': f'Meeting with ID {meeting_id} not found',
                'debug': {
                    'meeting_id': meeting_id,
                    'available_meetings': list(GroupMeeting.objects.values_list('pk', 'title'))
                }
            })
        except Exception as e:
            logger.error(f"Unexpected error in AgendaItemCreateAjaxView: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return JsonResponse({
                'success': False,
                'error': f'Unexpected error: {str(e)}',
                'debug': {
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'traceback': traceback.format_exc(),
                    'request_data': dict(request.POST),
                    'meeting_id': meeting_id
                }
            })


class AgendaItemUpdateAjaxView(LoginRequiredMixin, UserPassesTestMixin, View):
    """AJAX view for updating agenda items"""
    
    def test_func(self):
        """Check if user has permission to update agenda items"""
        return self.request.user.is_superuser

    def post(self, request, agenda_item_id):
        """Update an agenda item via AJAX"""
        from .models import AgendaItem
        from django.http import JsonResponse
        import traceback
        import logging
        
        logger = logging.getLogger(__name__)
        
        try:
            # Debug: Log the request data
            logger.debug(f"AJAX update request data: {request.POST}")
            logger.debug(f"Agenda Item ID: {agenda_item_id}")
            logger.debug(f"User: {request.user}")
            
            agenda_item = AgendaItem.objects.get(pk=agenda_item_id)
            logger.debug(f"Agenda item found: {agenda_item}")
            
            form = AgendaItemForm(request.POST, instance=agenda_item, meeting=agenda_item.meeting)
            logger.debug(f"Form data: {request.POST}")
            logger.debug(f"Form is valid: {form.is_valid()}")
            
            if not form.is_valid():
                logger.debug(f"Form errors: {form.errors}")
                return JsonResponse({
                    'success': False,
                    'error': 'Form validation failed',
                    'errors': form.errors,
                    'debug': {
                        'form_data': dict(request.POST),
                        'form_errors': form.errors
                    }
                })
            
            form.save()
            logger.debug(f"Agenda item updated: {agenda_item}")
            
            return JsonResponse({
                'success': True,
                'message': 'Agenda item updated successfully.',
                'agenda_item': {
                    'id': agenda_item.pk,
                    'title': agenda_item.title,
                    'description': agenda_item.description,
                    'order': agenda_item.order,
                    'parent_item': agenda_item.parent_item.pk if agenda_item.parent_item else None,
                    'level': agenda_item.level,
                }
            })
            
        except AgendaItem.DoesNotExist:
            logger.error(f"Agenda item with ID {agenda_item_id} not found")
            return JsonResponse({
                'success': False,
                'error': f'Agenda item with ID {agenda_item_id} not found',
                'debug': {
                    'agenda_item_id': agenda_item_id,
                    'available_items': list(AgendaItem.objects.values_list('pk', 'title'))
                }
            })
        except Exception as e:
            logger.error(f"Unexpected error in AgendaItemUpdateAjaxView: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return JsonResponse({
                'success': False,
                'error': f'Unexpected error: {str(e)}',
                'debug': {
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'traceback': traceback.format_exc(),
                    'request_data': dict(request.POST),
                    'agenda_item_id': agenda_item_id
                }
            })


class AgendaItemUpdateOrderAjaxView(LoginRequiredMixin, UserPassesTestMixin, View):
    """AJAX view for updating agenda item order"""
    
    def test_func(self):
        """Check if user has permission to update agenda items"""
        return self.request.user.is_superuser

    def post(self, request, meeting_id):
        """Update agenda item order via AJAX"""
        from .models import GroupMeeting
        from django.http import JsonResponse
        import json
        
        try:
            meeting = GroupMeeting.objects.get(pk=meeting_id)
            data = json.loads(request.body)
            item_orders = data.get('item_orders', [])
            
            for item_data in item_orders:
                item_id = item_data.get('id')
                new_order = item_data.get('order')
                parent_id = item_data.get('parent_item')
                
                try:
                    agenda_item = AgendaItem.objects.get(pk=item_id, meeting=meeting)
                    agenda_item.order = new_order
                    if parent_id:
                        agenda_item.parent_item = AgendaItem.objects.get(pk=parent_id, meeting=meeting)
                    else:
                        agenda_item.parent_item = None
                    agenda_item.save()
                except AgendaItem.DoesNotExist:
                    continue
            
            return JsonResponse({
                'success': True,
                'message': 'Agenda order updated successfully.'
            })
        except GroupMeeting.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Meeting not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


@login_required
def invite_member(request, pk):
    """Show form to invite a new member by email; send email with create-account link."""
    group = get_object_or_404(Group, pk=pk)
    if not (request.user.is_superuser or group.can_user_manage_group(request.user)):
        messages.error(request, _("You don't have permission to invite members to this group."))
        return redirect('group:group-detail', pk=group.pk)

    if request.method == 'POST':
        form = GroupInviteForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].strip().lower()
            # If user already exists, don't send duplicate invite; suggest adding as member instead
            existing_user = User.objects.filter(email__iexact=email).first()
            if existing_user:
                if group.members.filter(user=existing_user, is_active=True).exists():
                    messages.warning(request, _("A member with this email is already in the group."))
                else:
                    messages.info(request, _("A user with this email already has an account. You can add them as a member from 'Add Member'."))
                return render(request, 'group/member_invite.html', {'form': form, 'group': group})

            from urllib.parse import quote
            signup_url = request.build_absolute_uri(reverse('user-signup')) + '?email=' + quote(email)
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@klubtool.local')
            subject = _("Invitation to join {group_name}").format(group_name=group.name)
            context = {'group': group, 'signup_url': signup_url, 'email': email}
            try:
                plain_message = render_to_string('group/email/member_invite.txt', context)
                html_message = render_to_string('group/email/member_invite.html', context)
            except Exception:
                html_message = None
                plain_message = _("You have been invited to join the group \"{group_name}\". Create your account by visiting: {url}").format(
                    group_name=group.name, url=signup_url
                )
            send_mail(
                subject,
                plain_message,
                from_email,
                [email],
                html_message=html_message,
                fail_silently=False,
            )
            messages.success(request, _("Invitation email sent to {email}.").format(email=email))
            return redirect('group:group-detail', pk=group.pk)
    else:
        form = GroupInviteForm()

    return render(request, 'group/member_invite.html', {'form': form, 'group': group})


@login_required
def send_meeting_invites(request, pk):
    """Send meeting invites to all group members"""
    meeting = get_object_or_404(GroupMeeting, pk=pk)
    user = request.user
    meeting_group = meeting.group
    
    # Check permissions: only superusers, group admins, or leaders can send invites
    can_send = (
        user.is_superuser or 
        meeting_group.has_group_admin(user) or
        GroupMember.objects.filter(
            user=user,
            group=meeting_group,
            is_active=True,
            roles__name__in=['Leader', 'Deputy Leader']
        ).exists()
    )
    
    if not can_send:
        messages.error(request, _("You don't have permission to send meeting invites."))
        return redirect('group:meeting-detail', pk=meeting.pk)
    
    if meeting.status != 'scheduled':
        messages.error(request, _("Invites can only be sent when the meeting is scheduled."))
        return redirect('group:meeting-detail', pk=meeting.pk)
    
    # Get all active group members with email addresses
    members = GroupMember.objects.filter(
        group=meeting_group,
        is_active=True,
        user__email__isnull=False
    ).exclude(user__email='').select_related('user')
    
    if not members.exists():
        messages.warning(request, _("No group members with email addresses found."))
        return redirect('group:meeting-detail', pk=meeting.pk)
    
    # Get agenda items
    agenda_items = meeting.agenda_items.filter(is_active=True).order_by('order')
    
    # Prepare email content
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@klubtool.local')
    subject = _("Meeting Invitation: {meeting_title}").format(meeting_title=meeting.title)
    
    # Count successful and failed sends
    success_count = 0
    failed_count = 0
    failed_emails = []
    
    # Send email to each member
    for member in members:
        try:
            # Render email template
            email_context = {
                'meeting': meeting,
                'member': member,
                'agenda_items': agenda_items,
                'group': meeting_group,
            }
            
            # Try to render HTML email first, fallback to plain text
            try:
                message = render_to_string('group/email/meeting_invite.html', email_context)
                html_message = message
                plain_message = render_to_string('group/email/meeting_invite.txt', email_context)
            except:
                # Fallback to plain text if HTML template doesn't exist
                plain_message = render_to_string('group/email/meeting_invite.txt', email_context)
                html_message = None
            
            send_mail(
                subject,
                plain_message,
                from_email,
                [member.user.email],
                html_message=html_message,
                fail_silently=False,
            )
            success_count += 1
        except Exception as e:
            failed_count += 1
            failed_emails.append(member.user.email)
            # Log error but continue with other members
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send meeting invite to {member.user.email}: {str(e)}")
    
    # Show success/error messages and update meeting status
    if success_count > 0:
        messages.success(
            request, 
            _("Meeting invites sent successfully to {count} member(s).").format(count=success_count)
        )
        meeting.status = 'invited'
        meeting.save(update_fields=['status'])
    if failed_count > 0:
        messages.error(
            request,
            _("Failed to send invites to {count} member(s): {emails}").format(
                count=failed_count,
                emails=', '.join(failed_emails[:5]) + ('...' if len(failed_emails) > 5 else '')
            )
        )
    
    return redirect('group:meeting-detail', pk=meeting.pk)
