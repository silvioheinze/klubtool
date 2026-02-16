import logging
import requests
import json

from django.views.generic import TemplateView
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)

class HelpPageView(TemplateView):
    template_name = "help.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['host'] = self.request.get_host()
        return context


class HomePageView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['host'] = self.request.get_host()
        # Falls du den API_URL in der Template-Logik brauchst:
        context['API_URL'] = settings.API_URL
        
        # Check email verification status for authenticated users
        if self.request.user.is_authenticated:
            from allauth.account.models import EmailAddress
            try:
                email_address = EmailAddress.objects.get(
                    user=self.request.user,
                    email=self.request.user.email,
                    primary=True
                )
                context['email_verified'] = email_address.verified
                context['user_email'] = self.request.user.email
            except EmailAddress.DoesNotExist:
                context['email_verified'] = False
                context['user_email'] = self.request.user.email
        
        # Add group membership data for the current user
        if self.request.user.is_authenticated:
            try:
                from group.models import GroupMember
                from local.models import Local, Council
                
                # Get user's group memberships
                group_memberships = GroupMember.objects.filter(
                    user=self.request.user,
                    is_active=True
                ).select_related(
                    'group',
                    'group__party',
                    'group__party__local'
                ).order_by('group__name')
                
                context['group_memberships'] = group_memberships
                
                # Get unique locals and councils from memberships
                locals_from_memberships = set()
                councils_from_memberships = set()
                
                for membership in group_memberships:
                    if membership.group.party and membership.group.party.local:
                        locals_from_memberships.add(membership.group.party.local)
                        if hasattr(membership.group.party.local, 'council') and membership.group.party.local.council:
                            councils_from_memberships.add(membership.group.party.local.council)
                
                context['locals_from_memberships'] = sorted(locals_from_memberships, key=lambda x: x.name)
                context['councils_from_memberships'] = sorted(councils_from_memberships, key=lambda x: x.name)
                
            except ImportError:
                # If models are not available, set empty lists
                context['group_memberships'] = []
                context['locals_from_memberships'] = []
                context['councils_from_memberships'] = []
        else:
            context['group_memberships'] = []
            context['locals_from_memberships'] = []
            context['councils_from_memberships'] = []
        
        # Personal calendar: sessions (council + committee) and group meetings (always when authenticated)
        if self.request.user.is_authenticated:
            try:
                events = _get_personal_calendar_events(
                    self.request.user,
                    context.get('group_memberships', []),
                    context.get('councils_from_memberships', []),
                )
                context['personal_calendar_events'] = events
                # Paginate the list (6 per page) for the personal calendar list
                from django.core.paginator import Paginator
                paginator = Paginator(events, 6)
                req_page = self.request.GET.get('calendar_page', '1')
                try:
                    page_num = max(1, int(req_page))
                    page_num = min(page_num, paginator.num_pages or 1)
                except (TypeError, ValueError):
                    page_num = 1
                calendar_list_page = paginator.get_page(page_num)
                context['calendar_list_page'] = calendar_list_page
                # Prev/next URLs for list pagination (preserve calendar_month, calendar_year)
                from django.http import QueryDict
                from django.urls import reverse as reverse_url
                def _calendar_list_page_url(page_number):
                    q = QueryDict(mutable=True)
                    if self.request.GET.get('calendar_month'):
                        q['calendar_month'] = self.request.GET['calendar_month']
                    if self.request.GET.get('calendar_year'):
                        q['calendar_year'] = self.request.GET['calendar_year']
                    q['calendar_page'] = str(page_number)
                    return '{}?{}'.format(reverse_url('home'), q.urlencode())
                context['calendar_list_prev_url'] = _calendar_list_page_url(calendar_list_page.previous_page_number()) if calendar_list_page.has_previous() else None
                context['calendar_list_next_url'] = _calendar_list_page_url(calendar_list_page.next_page_number()) if calendar_list_page.has_next() else None
            except (ImportError, AttributeError):
                context['personal_calendar_events'] = []
                context['calendar_list_page'] = None
                context['calendar_list_prev_url'] = context['calendar_list_next_url'] = None
            # Monthly calendar view: month grid (use GET params if valid, else current month)
            try:
                events = context.get('personal_calendar_events', [])
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
                cal_month, cal_year, context['calendar_weeks'] = _build_month_calendar(events, cal_year, cal_month)
                context['calendar_month'] = cal_month
                context['calendar_year'] = cal_year
                import calendar as cal
                context['calendar_month_name'] = cal.month_name[cal_month]
                # Prev/next month for navigation
                if cal_month == 1:
                    context['calendar_prev_month'], context['calendar_prev_year'] = 12, cal_year - 1
                else:
                    context['calendar_prev_month'], context['calendar_prev_year'] = cal_month - 1, cal_year
                if cal_month == 12:
                    context['calendar_next_month'], context['calendar_next_year'] = 1, cal_year + 1
                else:
                    context['calendar_next_month'], context['calendar_next_year'] = cal_month + 1, cal_year
                from django.urls import reverse
                context['calendar_prev_url'] = '{}?calendar_month={}&calendar_year={}'.format(
                    reverse('home'), context['calendar_prev_month'], context['calendar_prev_year'])
                context['calendar_next_url'] = '{}?calendar_month={}&calendar_year={}'.format(
                    reverse('home'), context['calendar_next_month'], context['calendar_next_year'])
                # For "today" highlight: day number in current month, or None
                now = timezone.now()
                context['calendar_today_day'] = now.day if (now.year == cal_year and now.month == cal_month) else None
            except (ImportError, AttributeError):
                context['calendar_month'] = context['calendar_year'] = None
                context['calendar_weeks'] = []
                context['calendar_month_name'] = ''
                context['calendar_prev_url'] = context['calendar_next_url'] = ''
                context['calendar_today_day'] = None
        else:
            context['personal_calendar_events'] = []
            context['calendar_list_page'] = None
            context['calendar_list_prev_url'] = context['calendar_list_next_url'] = None
            context['calendar_month'] = context['calendar_year'] = None
            context['calendar_weeks'] = []
            context['calendar_month_name'] = ''
            context['calendar_prev_url'] = context['calendar_next_url'] = ''
            context['calendar_today_day'] = None

        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        # Return only the calendar list fragment for AJAX list pagination
        if request.GET.get('partial') == 'list':
            if request.user.is_authenticated:
                return render(request, 'pages/personal_calendar_list_partial.html', context)
            return HttpResponse(status=400)
        # Return only the calendar fragment for AJAX month navigation (require partial=1 in URL)
        wants_partial = request.GET.get('partial') == '1'
        # Debug: log GET params and what month we built
        logger.info(
            'calendar get: wants_partial=%s GET=%s -> month=%s year=%s name=%s',
            wants_partial,
            dict(request.GET),
            context.get('calendar_month'),
            context.get('calendar_year'),
            context.get('calendar_month_name'),
        )
        if wants_partial:
            if request.user.is_authenticated and context.get('calendar_weeks') is not None:
                logger.info('calendar partial: returning fragment for %s %s', context.get('calendar_month_name'), context.get('calendar_year'))
                return render(request, 'pages/calendar_month_partial.html', context)
            logger.warning('calendar partial: rejected (auth=%s weeks=%s)', request.user.is_authenticated, context.get('calendar_weeks'))
            return HttpResponse(status=400)
        return self.render_to_response(context)


class DocumentationPageView(TemplateView):
    template_name = "documentation.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['host'] = self.request.get_host()
        return context


def _get_personal_calendar_events(user, group_memberships, councils_from_memberships):
    """Build list of calendar event dicts for the user. Wrapper for display/export (no past events, no cancelled)."""
    from .calendar_utils import get_personal_calendar_events
    events = get_personal_calendar_events(user, group_memberships, councils_from_memberships, subscription_feed=False)
    # Ensure 'cancelled' key for backward compatibility with code that may not expect it
    for e in events:
        e.setdefault('cancelled', False)
    return events


def _build_month_calendar(events, year=None, month=None):
    """Build a month calendar structure (weeks of days with events) for the given month (default: current)."""
    import calendar
    now = timezone.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month
    events_by_day = {}
    for e in events:
        d = e['date']
        if getattr(d, 'tzinfo', None):
            d = timezone.localtime(d)
        if d.year == year and d.month == month:
            key = d.day
            events_by_day.setdefault(key, []).append(e)
    weeks = calendar.monthcalendar(year, month)
    calendar_weeks = []
    for week in weeks:
        row = []
        for day in week:
            if day == 0:
                row.append(None)
            else:
                row.append({'day': day, 'events': events_by_day.get(day, [])})
        calendar_weeks.append(row)
    return month, year, calendar_weeks


@login_required
def personal_calendar_export_ics(request):
    """Export the user's personal calendar (council/committee sessions + group meetings) as ICS."""
    try:
        from group.models import GroupMember
        from local.models import Local, Council
    except ImportError:
        return redirect('home')

    group_memberships = GroupMember.objects.filter(
        user=request.user,
        is_active=True,
    ).select_related('group', 'group__party', 'group__party__local').order_by('group__name')

    locals_from_memberships = set()
    councils_from_memberships = set()
    for membership in group_memberships:
        if membership.group.party and membership.group.party.local:
            locals_from_memberships.add(membership.group.party.local)
            if getattr(membership.group.party.local, 'council', None):
                councils_from_memberships.add(membership.group.party.local.council)
    councils_from_memberships = sorted(councils_from_memberships, key=lambda x: x.name)

    events = _get_personal_calendar_events(request.user, group_memberships, councils_from_memberships)

    from .calendar_utils import build_personal_calendar_ics
    ics_file = build_personal_calendar_ics(events, request)

    response = HttpResponse(ics_file, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="personal-calendar.ics"'
    return response


def calendar_subscription_feed(request, token):
    """
    Calendar subscription feed (WebCal). Token-based auth; no login required.
    Returns personal calendar ICS. Access control verified on every request.
    Cached for successful responses to handle high-frequency polling.
    """
    from django.core.exceptions import PermissionDenied
    from django.core.cache import cache
    from django.conf import settings
    from user.models import CalendarSubscriptionToken
    from group.models import GroupMember
    from .calendar_utils import get_personal_calendar_events, build_personal_calendar_ics

    subscription = CalendarSubscriptionToken.lookup(token)
    if not subscription:
        raise PermissionDenied("Invalid or expired subscription link.")

    user = subscription.user
    if not user.is_active:
        raise PermissionDenied("Subscription no longer active.")

    cache_ttl = getattr(settings, 'CALENDAR_SUBSCRIPTION_CACHE_TTL', 900)
    cache_key = f"calendar_sub:{subscription.token_hash}"
    ics_content = cache.get(cache_key)
    if ics_content is None:
        group_memberships = GroupMember.objects.filter(
            user=user,
            is_active=True,
        ).select_related('group', 'group__party', 'group__party__local').order_by('group__name')

        councils_from_memberships = []
        for membership in group_memberships:
            if membership.group.party and getattr(membership.group.party, 'local', None):
                local = membership.group.party.local
                if getattr(local, 'council', None):
                    councils_from_memberships.append(local.council)
        councils_from_memberships = sorted(set(councils_from_memberships), key=lambda x: x.name)

        events = get_personal_calendar_events(user, group_memberships, councils_from_memberships, subscription_feed=True)
        ics_content = build_personal_calendar_ics(events, request)
        cache.set(cache_key, ics_content, cache_ttl)

    subscription.update_last_used()

    response = HttpResponse(ics_content, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = 'inline; filename="personal-calendar.ics"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
def personal_calendar_export_pdf(request):
    """Export the user's personal calendar (council/committee sessions + group meetings) as PDF."""
    try:
        from django.template.loader import render_to_string
        from django.http import HttpResponse
        from weasyprint import HTML, CSS
        from group.models import GroupMember
        from local.models import Local, Council
    except ImportError:
        return redirect('home')

    group_memberships = GroupMember.objects.filter(
        user=request.user,
        is_active=True,
    ).select_related('group', 'group__party', 'group__party__local').order_by('group__name')

    locals_from_memberships = set()
    councils_from_memberships = set()
    for membership in group_memberships:
        if membership.group.party and membership.group.party.local:
            locals_from_memberships.add(membership.group.party.local)
            if getattr(membership.group.party.local, 'council', None):
                councils_from_memberships.add(membership.group.party.local.council)
    councils_from_memberships = sorted(councils_from_memberships, key=lambda x: x.name)

    events = _get_personal_calendar_events(request.user, group_memberships, councils_from_memberships)

    context = {
        'events': events,
        'user': request.user,
    }
    html_string = render_to_string('pages/personal_calendar_export_pdf.html', context)
    html = HTML(string=html_string)
    css = CSS(string='''
        @page { size: A4; margin: 15mm; }
        body { font-family: Arial, sans-serif; margin: 0; font-size: 10pt; }
        .header { text-align: center; margin-bottom: 20px; }
        .header h1 { font-size: 14pt; margin: 0 0 5px 0; }
        .header p { font-size: 10pt; margin: 2px 0; }
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
    first = (request.user.first_name or '').strip()
    last = (request.user.last_name or '').strip()
    safe = lambda s: ''.join(c if c not in '\\/:*?"<>|' else '_' for c in s).replace(' ', '_')
    if first or last:
        name_part = f'{safe(first)}_{safe(last)}' if last else safe(first)
    else:
        name_part = safe(request.user.username or 'User')
    filename = f'Kalender_{name_part}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response