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
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import json
from .models import Group, GroupMember, GroupMeeting, GroupEvent, GroupEventParticipation, AgendaItem, MinuteItem, GroupMeetingParticipation
from .forms import GroupForm, GroupFilterForm, GroupMemberForm, GroupMeetingForm, GroupEventForm, AgendaItemForm, MinuteItemForm, GroupInviteForm

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


def _get_group_calendar_events_for_month(group, year, month):
    """Return list of calendar event dicts (group meetings + council sessions + committee meetings) for the given month."""
    from datetime import date, timedelta
    start = date(year, month, 1)
    end = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    events = []
    badge_label = (group.calendar_badge_name or '').strip() or _('Group meeting')
    group_meetings = group.meetings.filter(
        is_active=True,
        scheduled_date__date__gte=start,
        scheduled_date__date__lte=end,
    ).order_by('scheduled_date')
    for m in group_meetings:
        events.append({
            'date': m.scheduled_date,
            'title': m.title or '',
            'url': m.get_absolute_url(),
            'type': 'group_meeting',
            'badge_label': badge_label,
        })
    # Party events (group events)
    group_events = group.events.filter(
        is_active=True,
        scheduled_date__date__gte=start,
        scheduled_date__date__lte=end,
    ).order_by('scheduled_date')
    for e in group_events:
        events.append({
            'date': e.scheduled_date,
            'title': e.title or '',
            'url': e.get_absolute_url(),
            'type': 'group_event',
            'badge_label': _('Party event'),
        })
    local = getattr(group.party, 'local', None)
    if local:
        try:
            from local.models import Session, CommitteeMeeting
            council = getattr(local, 'council', None)
            if council:
                council_sessions = Session.objects.filter(
                    council=council,
                    committee__isnull=True,
                    is_active=True,
                    scheduled_date__date__gte=start,
                    scheduled_date__date__lte=end,
                ).select_related('council').order_by('scheduled_date')
                session_badge = (council.calendar_badge_name or '').strip() or _('Council')
                for s in council_sessions:
                    events.append({
                        'date': s.scheduled_date,
                        'title': s.title or '',
                        'url': s.get_absolute_url(),
                        'type': 'session',
                        'badge_label': session_badge,
                    })
                committee_meetings = CommitteeMeeting.objects.filter(
                    committee__council=council,
                    is_active=True,
                    scheduled_date__date__gte=start,
                    scheduled_date__date__lte=end,
                ).select_related('committee').order_by('scheduled_date')
                for m in committee_meetings:
                    events.append({
                        'date': m.scheduled_date,
                        'title': m.title or '',
                        'url': m.get_absolute_url(),
                        'type': 'committee_meeting',
                        'badge_label': _('Committee'),
                    })
        except (ImportError, AttributeError):
            pass
    events.sort(key=lambda e: e['date'])
    return events


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
        # Allow superusers, users with group.view permission, group admins, or any active group member
        if self.request.user.is_superuser or self.request.user.has_role_permission('group.view'):
            return True
        group_pk = self.kwargs.get('pk')
        if group_pk is None:
            return False
        try:
            group_pk = int(group_pk)
        except (TypeError, ValueError):
            return False
        group = Group.objects.filter(pk=group_pk).first()
        if not group:
            return False
        return (
            group.can_user_manage_group(self.request.user)
            or GroupMember.objects.filter(user=self.request.user, group=group, is_active=True).exists()
        )

    def get_context_data(self, **kwargs):
        from pages.views import _build_month_calendar

        context = super().get_context_data(**kwargs)
        user = self.request.user
        group = self.object
        # Permission flags: show edit/add buttons only to users who can access those views
        context['can_edit_group'] = (
            user.is_superuser
            or user.has_role_permission('group.edit')
            or group.can_user_manage_group(user)
        )
        context['can_add_meeting'] = user.is_superuser or group.can_user_manage_group(user)
        context['can_add_event'] = user.is_superuser or group.can_user_manage_group(user)
        is_member = GroupMember.objects.filter(user=user, group=group, is_active=True).exists()
        context['can_export_calendar_pdf'] = (
            user.is_superuser
            or user.has_role_permission('group.view')
            or group.can_user_manage_group(user)
            or is_member
        )
        context['can_invite_member'] = user.is_superuser or group.can_user_manage_group(user)
        context['can_add_member'] = user.is_superuser or user.has_role_permission('group.create')
        context['can_view_member'] = (
            user.is_superuser or user.has_role_permission('group.view')
        )
        context['can_edit_member'] = (
            user.is_superuser
            or user.has_role_permission('group.edit')
            or group.can_user_manage_group(user)
        )
        context['can_manage_roles'] = user.is_superuser
        context['members'] = self.object.members.select_related('user').filter(is_active=True).order_by('user__first_name', 'user__last_name', 'user__username')
        context['active_members'] = context['members'].filter(is_active=True)
        
        # Add meetings data (paginated, 10 per page)
        from django.core.paginator import Paginator
        from django.http import QueryDict
        meetings_qs = self.object.meetings.filter(is_active=True).order_by('-scheduled_date')
        context['total_meetings'] = meetings_qs.count()
        paginator = Paginator(meetings_qs, 10)
        req_page = self.request.GET.get('meetings_page', '1')
        try:
            page_num = max(1, int(req_page))
            page_num = min(page_num, paginator.num_pages or 1)
        except (TypeError, ValueError):
            page_num = 1
        context['meetings_page'] = paginator.get_page(page_num)
        detail_url = reverse('group:group-detail', kwargs={'pk': self.object.pk})

        def _meetings_page_url(page_number):
            q = QueryDict(mutable=True)
            if self.request.GET.get('calendar_month'):
                q['calendar_month'] = self.request.GET['calendar_month']
            if self.request.GET.get('calendar_year'):
                q['calendar_year'] = self.request.GET['calendar_year']
            q['meetings_page'] = str(page_number)
            return f'{detail_url}?{q.urlencode()}'

        meetings_page = context['meetings_page']
        context['meetings_prev_url'] = _meetings_page_url(meetings_page.previous_page_number()) if meetings_page.has_previous() else None
        context['meetings_next_url'] = _meetings_page_url(meetings_page.next_page_number()) if meetings_page.has_next() else None

        # Add available roles for role management
        from user.models import Role
        context['available_roles'] = Role.objects.filter(is_active=True).order_by('name')

        # Monthly calendar for this group's meetings
        now = timezone.now()
        req_month = self.request.GET.get('calendar_month')
        req_year = self.request.GET.get('calendar_year')
        try:
            cal_month = int(req_month) if req_month else now.month
            cal_year = int(req_year) if req_year else now.year
            if cal_month < 1 or cal_month > 12 or cal_year < 2000 or cal_year > 2100:
                cal_month, cal_year = now.month, now.year
        except (TypeError, ValueError):
            cal_month, cal_year = now.month, now.year
        events = _get_group_calendar_events_for_month(self.object, cal_year, cal_month)
        cal_month, cal_year, context['calendar_weeks'] = _build_month_calendar(events, cal_year, cal_month)
        context['calendar_month'] = cal_month
        context['calendar_year'] = cal_year
        import calendar as cal_module
        context['calendar_month_name'] = cal_module.month_name[cal_month]
        context['calendar_today_day'] = now.day if (now.year == cal_year and now.month == cal_month) else None
        if cal_month == 1:
            prev_month, prev_year = 12, cal_year - 1
        else:
            prev_month, prev_year = cal_month - 1, cal_year
        if cal_month == 12:
            next_month, next_year = 1, cal_year + 1
        else:
            next_month, next_year = cal_month + 1, cal_year
        context['calendar_prev_url'] = f'{detail_url}?calendar_month={prev_month}&calendar_year={prev_year}'
        context['calendar_next_url'] = f'{detail_url}?calendar_month={next_month}&calendar_year={next_year}'
        context['calendar_today_url'] = f'{detail_url}?calendar_month={now.month}&calendar_year={now.year}'
        context['calendar_export_pdf_url'] = (
            reverse('group:group-calendar-export-pdf', kwargs={'pk': self.object.pk})
            + f'?calendar_year={cal_year}'
        )
        context['group_meetings_export_pdf_url'] = (
            reverse('group:group-meetings-export-pdf', kwargs={'pk': self.object.pk})
            + f'?calendar_year={cal_year}'
        )
        # Upcoming party events (preview for group detail)
        context['upcoming_events'] = (
            self.object.events.filter(is_active=True, scheduled_date__gte=now)
            .order_by('scheduled_date')[:5]
        )
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        if request.GET.get('partial') == 'calendar':
            if context.get('calendar_weeks') is not None:
                return render(request, 'group/group_calendar_partial.html', context)
            return HttpResponse(status=400)
        if request.GET.get('partial') == 'meetings':
            return render(request, 'group/group_meetings_list_partial.html', context)
        return self.render_to_response(context)


@login_required
def group_calendar_export_pdf(request, pk):
    """Export the group's calendar for the full year (sessions, committee meetings, group meetings) as PDF."""
    group = get_object_or_404(Group, pk=pk)
    is_member = GroupMember.objects.filter(user=request.user, group=group, is_active=True).exists()
    if not (
        request.user.is_superuser
        or request.user.has_role_permission('group.view')
        or group.can_user_manage_group(request.user)
        or is_member
    ):
        messages.error(request, _("You don't have permission to access this page."))
        return redirect('group:group-detail', pk=pk)
    now = timezone.now()
    req_year = request.GET.get('calendar_year')
    try:
        cal_year = int(req_year) if req_year else now.year
        if cal_year < 2000 or cal_year > 2100:
            cal_year = now.year
    except (TypeError, ValueError):
        cal_year = now.year
    events = []
    for month in range(1, 13):
        events.extend(_get_group_calendar_events_for_month(group, cal_year, month))
    events.sort(key=lambda e: e['date'])
    try:
        from weasyprint import HTML, CSS
        context = {
            'group': group,
            'events': events,
            'calendar_year': cal_year,
        }
        html_string = render_to_string('group/group_calendar_export_pdf.html', context)
        html = HTML(string=html_string)
        css = CSS(string='''
            @page { size: A4; margin: 15mm; }
            body { font-family: Arial, sans-serif; margin: 0; font-size: 10pt; }
            .header { text-align: center; margin-bottom: 20px; }
            .header h1 { font-size: 14pt; margin: 0 0 5px 0; }
            .calendar-table { width: 100%; border-collapse: collapse; margin-top: 15px; page-break-inside: auto; }
            .calendar-table thead { display: table-header-group; }
            .calendar-table tbody tr { page-break-inside: avoid; }
            .calendar-table th, .calendar-table td { border: 1px solid #333; padding: 8px; text-align: left; vertical-align: middle; }
            .calendar-table th { background-color: #f2f2f2; font-weight: bold; }
            .calendar-table td:first-child { width: 20%; white-space: nowrap; }
            .calendar-table td:nth-child(2) { width: 80%; }
            .no-events { text-align: center; color: #666; font-style: italic; margin: 40px 0; }
            .footer { margin-top: 30px; padding-top: 15px; border-top: 1px solid #ddd; text-align: center; color: #666; font-size: 8pt; }
        ''')
        pdf = html.write_pdf(stylesheets=[css])
        response = HttpResponse(pdf, content_type='application/pdf')
        export_date = timezone.now().date().strftime('%Y-%m-%d')
        filename = f'Klubkalender_{export_date}.pdf'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except ImportError:
        messages.error(request, _("PDF export is not available."))
        return redirect('group:group-detail', pk=pk)


@login_required
def group_meetings_export_pdf(request, pk):
    """Export only the group's meetings (no council sessions, no committee meetings) as PDF for a year."""
    group = get_object_or_404(Group, pk=pk)
    is_member = GroupMember.objects.filter(user=request.user, group=group, is_active=True).exists()
    if not (
        request.user.is_superuser
        or request.user.has_role_permission('group.view')
        or group.can_user_manage_group(request.user)
        or is_member
    ):
        messages.error(request, _("You don't have permission to access this page."))
        return redirect('group:group-detail', pk=pk)
    now = timezone.now()
    req_year = request.GET.get('calendar_year')
    try:
        cal_year = int(req_year) if req_year else now.year
        if cal_year < 2000 or cal_year > 2100:
            cal_year = now.year
    except (TypeError, ValueError):
        cal_year = now.year
    meetings = group.meetings.filter(
        is_active=True,
        scheduled_date__year=cal_year,
    ).order_by('scheduled_date')
    events = [{'date': m.scheduled_date, 'title': m.title or ''} for m in meetings]
    try:
        from weasyprint import HTML, CSS
        context = {
            'group': group,
            'events': events,
            'calendar_year': cal_year,
        }
        html_string = render_to_string('group/group_meetings_export_pdf.html', context)
        html = HTML(string=html_string)
        css = CSS(string='''
            @page { size: A4; margin: 15mm; }
            body { font-family: Arial, sans-serif; margin: 0; font-size: 10pt; }
            .header { text-align: center; margin-bottom: 20px; }
            .header h1 { font-size: 14pt; margin: 0 0 5px 0; }
            .calendar-table { width: 100%; border-collapse: collapse; margin-top: 15px; page-break-inside: auto; }
            .calendar-table thead { display: table-header-group; }
            .calendar-table tbody tr { page-break-inside: avoid; }
            .calendar-table th, .calendar-table td { border: 1px solid #333; padding: 8px; text-align: left; vertical-align: middle; }
            .calendar-table th { background-color: #f2f2f2; font-weight: bold; }
            .calendar-table td:first-child { width: 20%; white-space: nowrap; }
            .calendar-table td:nth-child(2) { width: 80%; }
            .no-events { text-align: center; color: #666; font-style: italic; margin: 40px 0; }
            .footer { margin-top: 30px; padding-top: 15px; border-top: 1px solid #ddd; text-align: center; color: #666; font-size: 8pt; }
        ''')
        pdf = html.write_pdf(stylesheets=[css])
        response = HttpResponse(pdf, content_type='application/pdf')
        export_date = timezone.now().date().strftime('%Y-%m-%d')
        safe_name = "".join(c if c.isalnum() or c in ' -_' else '_' for c in group.name)[:50]
        filename = f'Group_meetings_{safe_name.strip() or group.pk}_{export_date}.pdf'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except ImportError:
        messages.error(request, _("PDF export is not available."))
        return redirect('group:group-detail', pk=pk)


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
        return reverse('group:group-list')

    def form_valid(self, form):
        messages.success(self.request, f"Member '{form.instance.user.username}' added to group '{form.instance.group.name}' successfully.")
        return super().form_valid(form)

class GroupMemberUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = GroupMember
    form_class = GroupMemberForm
    template_name = 'group/member_form.html'

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
        return reverse('group:group-list')

    def form_valid(self, form):
        messages.success(self.request, f"Membership updated successfully.")
        return super().form_valid(form)

class GroupMemberDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = GroupMember
    template_name = 'group/member_confirm_delete.html'

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_role_permission('group.delete')

    def get_success_url(self):
        """Redirect to the group detail page after deletion"""
        if hasattr(self, '_deleted_member_group_pk'):
            return reverse('group:group-detail', kwargs={'pk': self._deleted_member_group_pk})
        return reverse('group:group-list')

    def delete(self, request, *args, **kwargs):
        member = self.get_object()
        self._deleted_member_group_pk = member.group.pk
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
        """Allow superuser or any user who is an active member of at least one group."""
        if self.request.user.is_superuser:
            return True
        return GroupMember.objects.filter(user=self.request.user, is_active=True).exists()

    def get_queryset(self):
        """Filter queryset: superusers see all meetings; others see only meetings of their groups."""
        user = self.request.user
        base = GroupMeeting.objects.all().select_related('group', 'created_by').order_by('-scheduled_date')
        if user.is_superuser:
            queryset = base
        else:
            user_group_ids = set(
                GroupMember.objects.filter(user=user, is_active=True).values_list('group_id', flat=True).distinct()
            )
            queryset = base.filter(group_id__in=user_group_ids) if user_group_ids else base.none()
        
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
        """Allow superuser, group managers, or any active member of the meeting's group."""
        if self.request.user.is_superuser:
            return True
        meeting_pk = self.kwargs.get('pk')
        if meeting_pk is None:
            return False
        try:
            meeting_pk = int(meeting_pk)
        except (TypeError, ValueError):
            return False
        meeting = GroupMeeting.objects.filter(pk=meeting_pk).select_related('group').first()
        if not meeting:
            return False
        return (
            meeting.group.can_user_manage_group(self.request.user)
            or GroupMember.objects.filter(user=self.request.user, group=meeting.group, is_active=True).exists()
        )

    def get_context_data(self, **kwargs):
        """Add agenda items and minute items (when invited) to context"""
        context = super().get_context_data(**kwargs)
        context['agenda_items'] = self.object.agenda_items.filter(is_active=True).order_by('order')
        if self.object.status == 'invited':
            context['minute_items'] = self.object.minute_items.filter(is_active=True).order_by('order')
        else:
            context['minute_items'] = []
        # Check if user can manage the meeting's group; all members can view meeting details
        user = self.request.user
        meeting_group = self.object.group
        can_manage = meeting_group.can_user_manage_group(user)
        is_member = GroupMember.objects.filter(user=user, group=meeting_group, is_active=True).exists()
        context['can_view_meeting_details'] = can_manage or is_member
        context['can_send_invites'] = can_manage
        context['can_edit_meeting'] = can_manage
        context['can_manage_agenda'] = can_manage
        context['can_manage_minutes'] = can_manage
        context['can_cancel_meeting'] = can_manage
        context['can_toggle_participation'] = can_manage
        
        # Add group members and participation data
        members = meeting_group.members.filter(is_active=True).select_related('user').order_by('user__last_name', 'user__first_name')
        context['group_members'] = members
        
        # Get participation records for this meeting
        participations = {
            p.member_id: p.is_present
            for p in GroupMeetingParticipation.objects.filter(meeting=self.object).select_related('member')
        }
        context['participations'] = participations
        # Count present members
        context['total_present'] = sum(1 for is_present in participations.values() if is_present)
        
        return context


@login_required
@require_http_methods(["POST"])
def toggle_meeting_participation(request, meeting_pk, member_pk):
    """AJAX view to toggle participation/presence of a member in a meeting"""
    # Check permissions - user must be superuser or can manage the meeting's group
    meeting = get_object_or_404(GroupMeeting, pk=meeting_pk)
    if not (request.user.is_superuser or meeting.group.can_user_manage_group(request.user)):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        member = get_object_or_404(GroupMember, pk=member_pk)
        
        # Verify member belongs to the meeting's group
        if member.group_id != meeting.group_id:
            return JsonResponse({'error': 'Member does not belong to this meeting\'s group'}, status=400)
        
        # Get or create participation record
        participation, created = GroupMeetingParticipation.objects.get_or_create(
            meeting=meeting,
            member=member,
            defaults={'is_present': True}
        )
        
        # Toggle presence
        participation.is_present = not participation.is_present
        participation.save(update_fields=['is_present'])
        
        # Count total present
        total_present = GroupMeetingParticipation.objects.filter(meeting=meeting, is_present=True).count()
        total_members = meeting.group.members.filter(is_active=True).count()
        
        return JsonResponse({
            'success': True,
            'is_present': participation.is_present,
            'total_present': total_present,
            'total_members': total_members
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


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


@login_required
def group_meetings_export_ics(request, pk):
    """Export all group meetings of a group as one ICS calendar file."""
    group = get_object_or_404(Group, pk=pk)
    is_member = GroupMember.objects.filter(user=request.user, group=group, is_active=True).exists()
    if not (
        request.user.is_superuser
        or request.user.has_role_permission('group.view')
        or group.can_user_manage_group(request.user)
        or is_member
    ):
        messages.error(request, _("You don't have permission to access this page."))
        return redirect('group:group-detail', pk=pk)

    def escape_ics_text(text):
        if not text:
            return ""
        text = str(text)
        text = text.replace('\\', '\\\\')
        text = text.replace(',', '\\,')
        text = text.replace(';', '\\;')
        text = text.replace('\n', '\\n')
        return text

    meetings = group.meetings.filter(is_active=True).order_by('scheduled_date')
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Klubtool//Group Meetings//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for meeting in meetings:
        dtstart = meeting.scheduled_date
        if not timezone.is_aware(dtstart):
            dtstart = timezone.make_aware(dtstart)
        dtstart_utc = dtstart.astimezone(timezone.UTC)
        dtend_utc = dtstart_utc + timezone.timedelta(hours=1)
        dtstart_str = dtstart_utc.strftime('%Y%m%dT%H%M%SZ')
        dtend_str = dtend_utc.strftime('%Y%m%dT%H%M%SZ')
        uid = f"group-meeting-{meeting.pk}@{request.get_host()}"
        created = meeting.created_at
        if not timezone.is_aware(created):
            created = timezone.make_aware(created)
        dtstamp_str = created.astimezone(timezone.UTC).strftime('%Y%m%dT%H%M%SZ')
        meeting_url = request.build_absolute_uri(reverse('group:meeting-detail', args=[meeting.pk]))
        event_lines = [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTART:{dtstart_str}",
            f"DTEND:{dtend_str}",
            f"SUMMARY:{escape_ics_text(meeting.title)}",
            f"DTSTAMP:{dtstamp_str}",
            f"URL:{meeting_url}",
        ]
        if meeting.description:
            event_lines.append(f"DESCRIPTION:{escape_ics_text(meeting.description)}")
        if meeting.location:
            event_lines.append(f"LOCATION:{escape_ics_text(meeting.location)}")
        event_lines.extend(["STATUS:CONFIRMED", "SEQUENCE:0", "END:VEVENT"])
        lines.extend(event_lines)
    lines.append("END:VCALENDAR")
    ics_file = "\r\n".join(lines)
    response = HttpResponse(ics_file, content_type='text/calendar; charset=utf-8')
    safe_name = "".join(c if c.isalnum() or c in ' -_' else '_' for c in group.name)[:50]
    filename = f"group_meetings_{safe_name.strip() or group.pk}.ics"
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


# Group Event (Party Event) Views
class GroupEventListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """List party events for a group"""
    model = GroupEvent
    context_object_name = 'events'
    template_name = 'group/event_list.html'
    paginate_by = 20

    def test_func(self):
        group_pk = self.kwargs.get('group_pk')
        group = get_object_or_404(Group, pk=group_pk)
        if self.request.user.is_superuser or group.can_user_manage_group(self.request.user):
            return True
        return GroupMember.objects.filter(user=self.request.user, group=group, is_active=True).exists()

    def get_queryset(self):
        group_pk = self.kwargs.get('group_pk')
        return GroupEvent.objects.filter(group_id=group_pk, is_active=True).select_related('group', 'created_by').order_by('-scheduled_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['group'] = get_object_or_404(Group, pk=self.kwargs['group_pk'])
        context['can_add_event'] = context['group'].can_user_manage_group(self.request.user) or self.request.user.is_superuser
        now = timezone.now()
        req_month = self.request.GET.get('calendar_month')
        req_year = self.request.GET.get('calendar_year')
        try:
            cal_month = int(req_month) if req_month else now.month
            cal_year = int(req_year) if req_year else now.year
            if cal_month < 1 or cal_month > 12:
                cal_month = now.month
            if cal_year < 2000 or cal_year > 2100:
                cal_year = now.year
        except (TypeError, ValueError):
            cal_month, cal_year = now.month, now.year
        context['calendar_weeks'] = _build_event_list_calendar(
            context['group'], cal_year, cal_month
        )
        context['calendar_month'] = cal_month
        context['calendar_year'] = cal_year
        return context


def _build_event_list_calendar(group, year, month):
    """Build calendar weeks for event list page (reuse group calendar logic)."""
    from datetime import date, timedelta
    import calendar as cal_mod
    start = date(year, month, 1)
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    events = _get_group_calendar_events_for_month(group, year, month)
    events_by_day = {}
    for e in events:
        d = e['date'].date() if hasattr(e['date'], 'date') else e['date']
        events_by_day.setdefault(d, []).append(e)
    first_weekday = cal_mod.weekday(year, month, 1)
    start_offset = (first_weekday - 0) % 7
    days_in_month = cal_mod.monthrange(year, month)[1]
    weeks = []
    day_num = 1
    week = []
    for _ in range(start_offset):
        week.append(None)
    while day_num <= days_in_month:
        d = date(year, month, day_num)
        cell_events = events_by_day.get(d, [])
        week.append({'day': day_num, 'events': cell_events})
        if len(week) == 7:
            weeks.append(week)
            week = []
        day_num += 1
    if week:
        while len(week) < 7:
            week.append(None)
        weeks.append(week)
    return weeks


class GroupEventCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Create a party event"""
    model = GroupEvent
    form_class = GroupEventForm
    template_name = 'group/event_form.html'

    def test_func(self):
        group_pk = self.kwargs.get('group_pk')
        group = get_object_or_404(Group, pk=group_pk)
        return self.request.user.is_superuser or group.can_user_manage_group(self.request.user)

    def get_initial(self):
        initial = super().get_initial()
        initial['group'] = self.kwargs.get('group_pk')
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['group'] = get_object_or_404(Group, pk=self.kwargs['group_pk'])
        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        if not form.instance.group_id:
            form.instance.group = get_object_or_404(Group, pk=self.kwargs['group_pk'])
        messages.success(self.request, _("Event '%(title)s' created successfully.") % {'title': form.instance.title})
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('group:event-list', kwargs={'group_pk': self.object.group.pk})


class GroupEventDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Detail view for a party event"""
    model = GroupEvent
    context_object_name = 'event'
    template_name = 'group/event_detail.html'

    def test_func(self):
        event = self.get_object()
        if self.request.user.is_superuser:
            return True
        return GroupMember.objects.filter(
            user=self.request.user, group=event.group, is_active=True
        ).exists()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event = self.object
        context['can_edit_event'] = (
            self.request.user.is_superuser or event.group.can_user_manage_group(self.request.user)
        )
        attending = GroupEventParticipation.objects.filter(
            event=event, will_attend=True
        ).select_related('member__user').order_by('member__user__last_name', 'member__user__first_name')
        context['attending_members'] = attending
        context['attending_count'] = attending.count()
        member = GroupMember.objects.filter(
            user=self.request.user, group=event.group, is_active=True
        ).first()
        context['user_member'] = member
        if member:
            part = GroupEventParticipation.objects.filter(event=event, member=member).first()
            context['user_will_attend'] = part.will_attend if part else False
        else:
            context['user_will_attend'] = False
        return context


class GroupEventUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Update a party event"""
    model = GroupEvent
    form_class = GroupEventForm
    template_name = 'group/event_form.html'
    context_object_name = 'event'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['group'] = self.object.group
        return context

    def test_func(self):
        event = self.get_object()
        return (
            self.request.user.is_superuser
            or event.group.can_user_manage_group(self.request.user)
            or event.created_by_id == self.request.user.pk
        )

    def get_success_url(self):
        return reverse('group:event-detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, _("Event '%(title)s' updated successfully.") % {'title': form.instance.title})
        return super().form_valid(form)


class GroupEventDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Delete a party event"""
    model = GroupEvent
    template_name = 'group/event_confirm_delete.html'
    context_object_name = 'event'

    def test_func(self):
        event = self.get_object()
        return (
            self.request.user.is_superuser
            or event.group.can_user_manage_group(self.request.user)
            or event.created_by_id == self.request.user.pk
        )

    def get_success_url(self):
        return reverse('group:event-list', kwargs={'group_pk': self.object.group.pk})

    def delete(self, request, *args, **kwargs):
        event = self.get_object()
        messages.success(request, _("Event '%(title)s' deleted successfully.") % {'title': event.title})
        return super().delete(request, *args, **kwargs)


@login_required
@require_http_methods(["POST"])
def event_attend(request, pk):
    """RSVP: set will_attend=True for the current user. Redirect back to event detail."""
    event = get_object_or_404(GroupEvent, pk=pk)
    member = GroupMember.objects.filter(
        user=request.user, group=event.group, is_active=True
    ).first()
    if not member:
        messages.error(request, _("You must be a group member to RSVP."))
        return redirect('group:event-detail', pk=pk)
    will_attend = request.POST.get('will_attend') == '1'
    part, created = GroupEventParticipation.objects.get_or_create(
        event=event, member=member, defaults={'will_attend': will_attend}
    )
    part.will_attend = will_attend
    part.save(update_fields=['will_attend', 'updated_at'])
    if will_attend:
        messages.success(request, _("You are marked as attending this event."))
    else:
        messages.info(request, _("You are marked as not attending."))
    return redirect('group:event-detail', pk=pk)


@login_required
def event_export_ics(request, pk):
    """Export a single group event as ICS."""
    event = get_object_or_404(GroupEvent, pk=pk)
    is_member = GroupMember.objects.filter(
        user=request.user, group=event.group, is_active=True
    ).exists()
    if not (
        request.user.is_superuser
        or event.group.can_user_manage_group(request.user)
        or is_member
    ):
        messages.error(request, _("You don't have permission to access this page."))
        return redirect('group:event-detail', pk=pk)
    dtstart = event.scheduled_date
    if not timezone.is_aware(dtstart):
        dtstart = timezone.make_aware(dtstart)
    dtstart_utc = dtstart.astimezone(timezone.UTC)
    dtend_utc = dtstart_utc + timezone.timedelta(hours=1)
    dtstart_str = dtstart_utc.strftime('%Y%m%dT%H%M%SZ')
    dtend_str = dtend_utc.strftime('%Y%m%dT%H%M%SZ')
    uid = f"group-event-{event.pk}@{request.get_host()}"

    def escape_ics_text(text):
        if not text:
            return ""
        text = str(text).replace('\\', '\\\\').replace(',', '\\,').replace(';', '\\;').replace('\n', '\\n')
        return text

    ics_content = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Klubtool//Group Event//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTART:{dtstart_str}",
        f"DTEND:{dtend_str}",
        f"SUMMARY:{escape_ics_text(event.title)}",
    ]
    if event.description:
        ics_content.append(f"DESCRIPTION:{escape_ics_text(event.description)}")
    if event.location:
        ics_content.append(f"LOCATION:{escape_ics_text(event.location)}")
    created = event.created_at
    if not timezone.is_aware(created):
        created = timezone.make_aware(created)
    ics_content.append(f"DTSTAMP:{created.astimezone(timezone.UTC).strftime('%Y%m%dT%H%M%SZ')}")
    ics_content.append(f"URL:{request.build_absolute_uri(reverse('group:event-detail', args=[event.pk]))}")
    ics_content.extend(["STATUS:CONFIRMED", "SEQUENCE:0", "END:VEVENT", "END:VCALENDAR"])
    response = HttpResponse("\r\n".join(ics_content), content_type='text/calendar; charset=utf-8')
    safe_title = "".join(c if c.isalnum() or c in ' -_' else '_' for c in event.title)[:50]
    response['Content-Disposition'] = f'attachment; filename="event_{event.pk}_{safe_title.strip()}.ics"'
    return response


class GroupMeetingAgendaExportPDFView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for exporting group meeting agenda as PDF"""
    model = GroupMeeting
    context_object_name = 'meeting'
    template_name = 'group/meeting_agenda_export_pdf.html'

    def test_func(self):
        """Allow superuser, group managers, or any active member of the meeting's group."""
        if self.request.user.is_superuser:
            return True
        meeting_pk = self.kwargs.get('pk')
        if meeting_pk is None:
            return False
        try:
            meeting_pk = int(meeting_pk)
        except (TypeError, ValueError):
            return False
        meeting = GroupMeeting.objects.filter(pk=meeting_pk).select_related('group').first()
        if not meeting:
            return False
        return (
            meeting.group.can_user_manage_group(self.request.user)
            or GroupMember.objects.filter(user=self.request.user, group=meeting.group, is_active=True).exists()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['agenda_items'] = self.object.agenda_items.filter(is_active=True).order_by('order')
        return context

    def render_to_response(self, context, **response_kwargs):
        from django.template.loader import render_to_string
        from django.http import HttpResponse
        from weasyprint import HTML, CSS

        html_string = render_to_string(self.template_name, context)
        html = HTML(string=html_string)
        css = CSS(string='''
            @page { size: A4; margin: 15mm; }
            body { font-family: Arial, sans-serif; margin: 0; font-size: 10pt; }
            .header { text-align: center; margin-bottom: 20px; }
            .header h1 { font-size: 14pt; margin: 0 0 5px 0; }
            .header p { font-size: 10pt; margin: 2px 0; }
            .agenda-table { width: 100%; border-collapse: collapse; margin-top: 15px; page-break-inside: auto; }
            .agenda-table thead { display: table-header-group; }
            .agenda-table tbody tr { page-break-inside: avoid; }
            .agenda-table th, .agenda-table td { border: 1px solid #333; padding: 8px; text-align: left; vertical-align: top; }
            .agenda-table th { background-color: #f2f2f2; font-weight: bold; }
            .agenda-table td:first-child { width: 8%; text-align: center; font-weight: bold; }
            .agenda-table td:nth-child(2) { width: 92%; }
            .agenda-desc { font-size: 9pt; color: #444; margin-top: 4px; }
            .no-agenda { text-align: center; color: #666; font-style: italic; margin: 40px 0; }
            .footer { margin-top: 30px; padding-top: 15px; border-top: 1px solid #ddd; text-align: center; color: #666; font-size: 8pt; }
        ''')
        pdf = html.write_pdf(stylesheets=[css])
        response = HttpResponse(pdf, content_type='application/pdf')
        safe_title = ''.join(c if c.isalnum() or c in ' -_' else '_' for c in self.object.title)
        date_str = self.object.scheduled_date.strftime('%Y-%m-%d') if self.object.scheduled_date else ''
        filename = f"agenda_{safe_title}_{date_str}.pdf".replace(' ', '_')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class GroupMeetingMinutesExportPDFView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for exporting group meeting minutes as PDF"""
    model = GroupMeeting
    context_object_name = 'meeting'
    template_name = 'group/meeting_minutes_export_pdf.html'

    def test_func(self):
        """Allow superuser, group managers, or any active member of the meeting's group."""
        if self.request.user.is_superuser:
            return True
        meeting_pk = self.kwargs.get('pk')
        if meeting_pk is None:
            return False
        try:
            meeting_pk = int(meeting_pk)
        except (TypeError, ValueError):
            return False
        meeting = GroupMeeting.objects.filter(pk=meeting_pk).select_related('group').first()
        if not meeting:
            return False
        return (
            meeting.group.can_user_manage_group(self.request.user)
            or GroupMember.objects.filter(user=self.request.user, group=meeting.group, is_active=True).exists()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['minute_items'] = self.object.minute_items.filter(is_active=True).order_by('order')
        return context

    def render_to_response(self, context, **response_kwargs):
        from django.template.loader import render_to_string
        from django.http import HttpResponse
        from weasyprint import HTML, CSS

        html_string = render_to_string(self.template_name, context)
        html = HTML(string=html_string)
        css = CSS(string='''
            @page { size: A4; margin: 15mm; }
            body { font-family: Arial, sans-serif; margin: 0; font-size: 10pt; }
            .header { text-align: center; margin-bottom: 20px; }
            .header h1 { font-size: 14pt; margin: 0 0 5px 0; }
            .header p { font-size: 10pt; margin: 2px 0; }
            .minutes-table { width: 100%; border-collapse: collapse; margin-top: 15px; page-break-inside: auto; }
            .minutes-table thead { display: table-header-group; }
            .minutes-table tbody tr { page-break-inside: avoid; }
            .minutes-table th, .minutes-table td { border: 1px solid #333; padding: 8px; text-align: left; vertical-align: top; }
            .minutes-table th { background-color: #f2f2f2; font-weight: bold; }
            .minutes-table td:first-child { width: 8%; text-align: center; font-weight: bold; }
            .minutes-table td:nth-child(2) { width: 92%; }
            .minutes-desc { font-size: 9pt; color: #444; margin-top: 4px; }
            .minutes-desc p { margin: 2px 0; }
            .no-minutes { text-align: center; color: #666; font-style: italic; margin: 40px 0; }
            .footer { margin-top: 30px; padding-top: 15px; border-top: 1px solid #ddd; text-align: center; color: #666; font-size: 8pt; }
        ''')
        pdf = html.write_pdf(stylesheets=[css])
        response = HttpResponse(pdf, content_type='application/pdf')
        safe_title = ''.join(c if c.isalnum() or c in ' -_' else '_' for c in self.object.title)
        date_str = self.object.scheduled_date.strftime('%Y-%m-%d') if self.object.scheduled_date else ''
        filename = f"minutes_{safe_title}_{date_str}.pdf".replace(' ', '_')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


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

    def dispatch(self, request, *args, **kwargs):
        """Only allow delete when meeting status is scheduled"""
        obj = self.get_object()
        if obj.meeting.status != 'scheduled':
            messages.error(
                request,
                _('Agenda can only be modified when the meeting status is scheduled.'),
            )
            return redirect('group:meeting-detail', pk=obj.meeting.pk)
        return super().dispatch(request, *args, **kwargs)

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
            if meeting.status != 'scheduled':
                return JsonResponse({
                    'success': False,
                    'error': _('Agenda can only be modified when the meeting status is scheduled.'),
                }, status=403)
            
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
            if agenda_item.meeting.status != 'scheduled':
                return JsonResponse({
                    'success': False,
                    'error': _('Agenda can only be modified when the meeting status is scheduled.'),
                }, status=403)
            
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
            if meeting.status != 'scheduled':
                return JsonResponse({
                    'success': False,
                    'error': _('Agenda order can only be changed when the meeting status is scheduled.'),
                }, status=403)
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


# Minute item views (allowed when meeting status is 'invited')
def _can_manage_minutes(user, meeting):
    if user.is_superuser:
        return True
    return meeting.group.can_user_manage_group(user)


class MinuteItemCreateAjaxView(LoginRequiredMixin, View):
    """AJAX view for creating minute items (when meeting status is invited)."""
    def post(self, request, meeting_id):
        from django.http import JsonResponse
        meeting = get_object_or_404(GroupMeeting, pk=meeting_id)
        if meeting.status != 'invited':
            return JsonResponse({
                'success': False,
                'error': _('Minutes can only be modified when the meeting status is invited.'),
            }, status=403)
        if not _can_manage_minutes(request.user, meeting):
            return JsonResponse({'success': False, 'error': _('Permission denied.')}, status=403)
        form = MinuteItemForm(request.POST, meeting=meeting)
        if not form.is_valid():
            return JsonResponse({'success': False, 'error': 'Form validation failed', 'errors': form.errors})
        item = form.save(commit=False)
        item.meeting = meeting
        item.created_by = request.user
        from django.db.models import Max
        max_order = MinuteItem.objects.filter(meeting=meeting).aggregate(max_order=Max('order'))['max_order'] or 0
        item.order = max_order + 1
        item.parent_item = None
        item.save()
        return JsonResponse({
            'success': True,
            'minute_item': {'id': item.pk, 'title': item.title, 'description': item.description, 'order': item.order},
        })


class MinuteItemUpdateAjaxView(LoginRequiredMixin, View):
    """AJAX view for updating minute items."""
    def post(self, request, minute_item_id):
        from django.http import JsonResponse
        item = get_object_or_404(MinuteItem, pk=minute_item_id)
        if item.meeting.status != 'invited':
            return JsonResponse({
                'success': False,
                'error': _('Minutes can only be modified when the meeting status is invited.'),
            }, status=403)
        if not _can_manage_minutes(request.user, item.meeting):
            return JsonResponse({'success': False, 'error': _('Permission denied.')}, status=403)
        form = MinuteItemForm(request.POST, instance=item, meeting=item.meeting)
        if not form.is_valid():
            return JsonResponse({'success': False, 'error': 'Form validation failed', 'errors': form.errors})
        form.save()
        return JsonResponse({'success': True})


class MinuteItemDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting a minute item."""
    model = MinuteItem
    def test_func(self):
        obj = self.get_object()
        if not _can_manage_minutes(self.request.user, obj.meeting):
            return False
        return obj.meeting.status == 'invited'
    def get_success_url(self):
        return reverse('group:meeting-detail', kwargs={'pk': self.object.meeting.pk})
    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        messages.success(request, _('Minute item deleted.'))
        return redirect(self.get_success_url())
    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)


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
    
    # Show success/error messages and update meeting status; copy agenda to minute items on first send
    if success_count > 0:
        messages.success(
            request, 
            _("Meeting invites sent successfully to {count} member(s).").format(count=success_count)
        )
        meeting.status = 'invited'
        meeting.save(update_fields=['status'])
        # Copy all agenda items to minute items (only if no minute items exist yet)
        if not meeting.minute_items.exists():
            from .models import MinuteItem
            agenda_items_ordered = meeting.agenda_items.filter(is_active=True).order_by('order')
            agenda_to_minute = {}  # agenda_item.pk -> minute_item
            for agenda_item in agenda_items_ordered:
                parent_minute = agenda_to_minute.get(agenda_item.parent_item_id) if agenda_item.parent_item_id else None
                minute_item = MinuteItem.objects.create(
                    meeting=meeting,
                    title=agenda_item.title,
                    description=agenda_item.description or '',
                    order=agenda_item.order,
                    parent_item=parent_minute,
                    created_by=request.user,
                )
                agenda_to_minute[agenda_item.pk] = minute_item
    if failed_count > 0:
        messages.error(
            request,
            _("Failed to send invites to {count} member(s): {emails}").format(
                count=failed_count,
                emails=', '.join(failed_emails[:5]) + ('...' if len(failed_emails) > 5 else '')
            )
        )
    
    return redirect('group:meeting-detail', pk=meeting.pk)
