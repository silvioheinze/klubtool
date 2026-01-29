import logging
import requests
import json

from django.views.generic import TemplateView
from django.conf import settings

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
                from django.utils import timezone
                from datetime import timedelta
                from local.models import Session, CommitteeMember
                from group.models import GroupMeeting
                
                user_councils = context.get('councils_from_memberships', [])
                user_council_ids = [c.pk for c in user_councils]
                user_committee_ids = list(
                    CommitteeMember.objects.filter(
                        user=self.request.user,
                        is_active=True
                    ).values_list('committee_id', flat=True)
                )
                user_group_ids = [m.group_id for m in context.get('group_memberships', [])]
                
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
                        scheduled_date__lte=range_end
                    ).select_related('council', 'council__local').order_by('scheduled_date')
                    for s in council_sessions:
                        calendar_events.append({
                            'date': s.scheduled_date,
                            'title': s.title,
                            'url': s.get_absolute_url(),
                            'type': 'council_session',
                            'subtitle': s.council.name,
                            'location': getattr(s, 'location', '') or '',
                        })
                
                if user_committee_ids:
                    committee_sessions = Session.objects.filter(
                        committee_id__in=user_committee_ids,
                        is_active=True,
                        scheduled_date__gte=range_start,
                        scheduled_date__lte=range_end
                    ).select_related('committee', 'council').order_by('scheduled_date')
                    for s in committee_sessions:
                        calendar_events.append({
                            'date': s.scheduled_date,
                            'title': s.title,
                            'url': s.get_absolute_url(),
                            'type': 'committee_session',
                            'subtitle': s.committee.name if s.committee else s.council.name,
                            'location': getattr(s, 'location', '') or '',
                        })
                
                if user_group_ids:
                    group_meetings = GroupMeeting.objects.filter(
                        group_id__in=user_group_ids,
                        is_active=True,
                        scheduled_date__gte=range_start,
                        scheduled_date__lte=range_end
                    ).select_related('group').order_by('scheduled_date')
                    for m in group_meetings:
                        calendar_events.append({
                            'date': m.scheduled_date,
                            'title': m.title,
                            'url': m.get_absolute_url(),
                            'type': 'group_meeting',
                            'subtitle': m.group.name,
                            'location': getattr(m, 'location', '') or '',
                        })
                
                calendar_events.sort(key=lambda e: e['date'])
                context['personal_calendar_events'] = calendar_events
            except (ImportError, AttributeError):
                context['personal_calendar_events'] = []
        else:
            context['personal_calendar_events'] = []
        
        return context
    

class DocumentationPageView(TemplateView):
    template_name = "documentation.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['host'] = self.request.get_host()
        return context