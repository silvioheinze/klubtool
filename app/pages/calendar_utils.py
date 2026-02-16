"""
Shared calendar and ICS utilities for personal calendar export and subscription feed.
"""
from django.utils import timezone
from django.utils.translation import gettext as _

from datetime import timedelta


def _escape_ics_text(text):
    if not text:
        return ""
    text = str(text)
    text = text.replace('\\', '\\\\').replace(',', '\\,').replace(';', '\\;').replace('\n', '\\n')
    return text


def get_personal_calendar_events(user, group_memberships, councils_from_memberships, subscription_feed=False):
    """
    Build list of calendar event dicts (council sessions + committee meetings + group meetings) for the user.

    When subscription_feed=True:
    - Includes events from the past 30 days (for sync of cancellations)
    - Adds 'cancelled' flag for events with status=cancelled (Session, GroupMeeting)
    """
    from django.urls import reverse
    from django.db.models import Q
    from local.models import Session, CommitteeMeeting, CommitteeMember, CommitteeParticipationSubstitute, SessionExcuse
    from group.models import GroupMeeting

    user_council_ids = [c.pk for c in councils_from_memberships]
    user_committee_ids = list(
        CommitteeMember.objects.filter(user=user, is_active=True)
        .exclude(role='substitute_member')
        .values_list('committee_id', flat=True)
    )
    meeting_ids_where_user_is_substitute = list(
        CommitteeParticipationSubstitute.objects.filter(substitute_member__user=user)
        .values_list('committee_meeting_id', flat=True)
    )
    user_group_ids = [m.group_id for m in group_memberships]

    now = timezone.now()
    if subscription_feed:
        date_threshold = now - timedelta(days=30)
    else:
        date_threshold = now

    calendar_events = []

    if user_council_ids:
        council_sessions = Session.objects.filter(
            council_id__in=user_council_ids,
            committee__isnull=True,
            is_active=True,
            scheduled_date__gte=date_threshold,
        ).select_related('council', 'council__local').order_by('scheduled_date')

        excused_session_ids = set(
            SessionExcuse.objects.filter(user=user, session__in=council_sessions).values_list('session_id', flat=True)
        )
        for s in council_sessions:
            if s.pk in excused_session_ids:
                continue
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
                'cancelled': getattr(s, 'status', None) == 'cancelled',
            })

    if user_committee_ids or meeting_ids_where_user_is_substitute:
        committee_meetings = CommitteeMeeting.objects.filter(
            is_active=True,
            scheduled_date__gte=date_threshold,
        ).filter(
            (Q(committee_id__in=user_committee_ids) if user_committee_ids else Q(pk__in=[]))
            | (Q(pk__in=meeting_ids_where_user_is_substitute) if meeting_ids_where_user_is_substitute else Q(pk__in=[]))
        ).select_related('committee').order_by('scheduled_date')
        for m in committee_meetings:
            calendar_events.append({
                'date': m.scheduled_date,
                'title': m.title,
                'url': m.get_absolute_url(),
                'ics_export_url': reverse('local:committee-meeting-export-ics', args=[m.pk]),
                'type': 'committee_meeting',
                'badge_label': m.committee.get_committee_type_display(),
                'subtitle': m.committee.name,
                'location': getattr(m, 'location', '') or '',
                'pk': m.pk,
                'model': 'committeemeeting',
                'cancelled': False,
            })

    if user_group_ids:
        if subscription_feed:
            group_meetings = GroupMeeting.objects.filter(
                group_id__in=user_group_ids,
                scheduled_date__gte=date_threshold,
            ).filter(
                Q(is_active=True) | Q(status='cancelled')
            ).select_related('group').order_by('scheduled_date')
        else:
            group_meetings = GroupMeeting.objects.filter(
                group_id__in=user_group_ids,
                is_active=True,
                scheduled_date__gte=date_threshold,
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
                'cancelled': getattr(m, 'status', None) == 'cancelled',
            })

    calendar_events.sort(key=lambda e: e['date'])
    return calendar_events


def build_personal_calendar_ics(events, request, host=None):
    """
    Build ICS content (str) for the given events.
    Uses request for absolute URLs; host fallback for UID if request is None.
    """
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Klubtool//Personal Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    host = host or (request.get_host() if request else 'localhost')
    now_utc = timezone.now().astimezone(timezone.UTC)

    for event in events:
        dt = event['date']
        if not timezone.is_aware(dt):
            dt = timezone.make_aware(dt)
        dt_utc = dt.astimezone(timezone.UTC)
        dtend_utc = dt_utc + timedelta(hours=1)
        dtstart_str = dt_utc.strftime('%Y%m%dT%H%M%SZ')
        dtend_str = dtend_utc.strftime('%Y%m%dT%H%M%SZ')
        uid = f"{event['model']}-{event['pk']}@{host}"
        summary = _escape_ics_text(event['title'])
        desc = _escape_ics_text(event.get('subtitle', ''))
        loc = _escape_ics_text(event.get('location', ''))
        url_abs = request.build_absolute_uri(event['url']) if request and event.get('url') else ''
        cancelled = event.get('cancelled', False)

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
        lines.append(f"DTSTAMP:{now_utc.strftime('%Y%m%dT%H%M%SZ')}")
        lines.append("STATUS:CANCELLED" if cancelled else "STATUS:CONFIRMED")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)
