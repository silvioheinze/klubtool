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
            except (ImportError, AttributeError):
                context['personal_calendar_events'] = []
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
            context['calendar_month'] = context['calendar_year'] = None
            context['calendar_weeks'] = []
            context['calendar_month_name'] = ''
            context['calendar_prev_url'] = context['calendar_next_url'] = ''
            context['calendar_today_day'] = None

        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
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
    """Build list of calendar event dicts (council sessions + committee meetings + group meetings) for the user."""
    from datetime import timedelta
    from django.urls import reverse
    from local.models import Session, CommitteeMeeting, CommitteeMember
    from group.models import GroupMeeting

    user_council_ids = [c.pk for c in councils_from_memberships]
    user_committee_ids = list(
        CommitteeMember.objects.filter(user=user, is_active=True).values_list('committee_id', flat=True)
    )
    user_group_ids = [m.group_id for m in group_memberships]

    now = timezone.now()
    range_start = now - timedelta(days=7)
    range_end = now + timedelta(days=60)

    calendar_events = []

    if user_council_ids:
        council_sessions = Session.objects.filter(
            council_id__in=user_council_ids,
            committee__isnull=True,
            is_active=True,
            scheduled_date__gte=range_start,
            scheduled_date__lte=range_end,
        ).select_related('council', 'council__local').order_by('scheduled_date')
        for s in council_sessions:
            badge_name = (s.council.calendar_badge_name or '').strip()
            calendar_events.append({
                'date': s.scheduled_date,
                'title': s.title,
                'url': s.get_absolute_url(),
                'ics_export_url': reverse('local:session-export-ics', args=[s.pk]),
                'type': 'council_session',
                'badge_label': badge_name or _('Council'),
                'subtitle': s.council.name,
                'location': getattr(s, 'location', '') or '',
                'pk': s.pk,
                'model': 'session',
            })

    if user_committee_ids:
        committee_meetings = CommitteeMeeting.objects.filter(
            committee_id__in=user_committee_ids,
            is_active=True,
            scheduled_date__gte=range_start,
            scheduled_date__lte=range_end,
        ).select_related('committee').order_by('scheduled_date')
        for m in committee_meetings:
            calendar_events.append({
                'date': m.scheduled_date,
                'title': m.title,
                'url': m.get_absolute_url(),
                'ics_export_url': reverse('local:committee-meeting-export-ics', args=[m.pk]),
                'type': 'committee_meeting',
                'badge_label': _('Committee'),
                'subtitle': m.committee.name,
                'location': getattr(m, 'location', '') or '',
                'pk': m.pk,
                'model': 'committeemeeting',
            })

    if user_group_ids:
        group_meetings = GroupMeeting.objects.filter(
            group_id__in=user_group_ids,
            is_active=True,
            scheduled_date__gte=range_start,
            scheduled_date__lte=range_end,
        ).select_related('group').order_by('scheduled_date')
        for m in group_meetings:
            badge_name = (m.group.calendar_badge_name or '').strip()
            calendar_events.append({
                'date': m.scheduled_date,
                'title': m.title,
                'url': m.get_absolute_url(),
                'ics_export_url': reverse('group:meeting-export-ics', args=[m.pk]),
                'type': 'group_meeting',
                'badge_label': badge_name or _('Group meeting'),
                'subtitle': m.group.name,
                'location': getattr(m, 'location', '') or '',
                'pk': m.pk,
                'model': 'groupmeeting',
            })

    calendar_events.sort(key=lambda e: e['date'])
    return calendar_events


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


def _escape_ics_text(text):
    if not text:
        return ""
    text = str(text)
    text = text.replace('\\', '\\\\').replace(',', '\\,').replace(';', '\\;').replace('\n', '\\n')
    return text


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

    # Build ICS
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Klubtool//Personal Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for event in events:
        dt = event['date']
        if not timezone.is_aware(dt):
            dt = timezone.make_aware(dt)
        dt_utc = dt.astimezone(timezone.UTC)
        dtend_utc = dt_utc + timezone.timedelta(hours=1)
        dtstart_str = dt_utc.strftime('%Y%m%dT%H%M%SZ')
        dtend_str = dtend_utc.strftime('%Y%m%dT%H%M%SZ')
        uid = f"{event['model']}-{event['pk']}@{request.get_host()}"
        summary = _escape_ics_text(event['title'])
        desc = _escape_ics_text(event.get('subtitle', ''))
        loc = _escape_ics_text(event.get('location', ''))
        url_abs = request.build_absolute_uri(event['url']) if event.get('url') else ''

        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{uid}")
        lines.append(f"DTSTART:{dtstart_str}")
        lines.append(f"DTEND:{dtend_str}")
        lines.append(f"SUMMARY:{summary}")
        if desc:
            lines.append(f"DESCRIPTION:{desc}")
        if loc:
            lines.append(f"LOCATION:{loc}")
        if url_abs:
            lines.append(f"URL:{url_abs}")
        lines.append(f"DTSTAMP:{timezone.now().astimezone(timezone.UTC).strftime('%Y%m%dT%H%M%SZ')}")
        lines.append("STATUS:CONFIRMED")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    ics_file = "\r\n".join(lines)

    response = HttpResponse(ics_file, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="personal-calendar.ics"'
    return response