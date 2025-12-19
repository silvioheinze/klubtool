import logging
import requests
import json

from django.views.generic import TemplateView
from django.conf import settings
from django.utils.translation import gettext_lazy as _

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
        
        # Add motion statistics for authenticated users
        if self.request.user.is_authenticated:
            try:
                from motion.models import Motion
                from django.db.models import Count, Q
                from django.utils import timezone
                from datetime import timedelta
                
                # Get all motions the user can see (based on their groups/councils)
                user_groups = [m.group for m in context.get('group_memberships', [])]
                user_councils = context.get('councils_from_memberships', [])
                
                motions_queryset = Motion.objects.filter(is_active=True)
                
                # Filter by user's groups if they have any
                if user_groups:
                    motions_queryset = motions_queryset.filter(group__in=user_groups)
                # Or filter by user's councils if they have any
                elif user_councils:
                    motions_queryset = motions_queryset.filter(session__council__in=user_councils)
                
                # If user is superuser, show all motions
                if self.request.user.is_superuser:
                    motions_queryset = Motion.objects.filter(is_active=True)
                
                # Statistics by status - prepare data for charts
                status_counts = motions_queryset.values('status').annotate(count=Count('id')).order_by('status')
                context['motion_status_stats'] = {item['status']: item['count'] for item in status_counts}
                
                # Prepare status data for chart (ordered list)
                status_labels = {
                    'draft': _('Draft'),
                    'submitted': _('Submitted'),
                    'refer_to_committee': _('Refer to Committee'),
                    'approved': _('Approved'),
                    'rejected': _('Rejected'),
                    'withdrawn': _('Withdrawn'),
                    'not_admitted': _('Nicht zugelassen'),
                }
                context['motion_status_chart_data'] = [
                    {'label': status_labels.get(status, status), 'count': context['motion_status_stats'].get(status, 0)}
                    for status in status_labels.keys()
                ]
                
                # Statistics by type
                type_counts = motions_queryset.values('motion_type').annotate(count=Count('id')).order_by('motion_type')
                context['motion_type_stats'] = {item['motion_type']: item['count'] for item in type_counts}
                
                # Prepare session data for stacked bar chart
                from local.models import Session
                
                # Get sessions that have motions (from the filtered motions queryset)
                sessions_with_motions = Session.objects.filter(
                    motions__in=motions_queryset,
                    is_active=True
                ).distinct().order_by('-scheduled_date')[:10]  # Get last 10 sessions
                
                # Prepare session chart data with motion counts by type
                type_labels = {
                    'resolution': _('Resolutionsantrag'),
                    'general': _('General motion'),
                }
                
                # Prepare datasets for each type
                type_keys = list(type_labels.keys())
                session_labels = []
                datasets_data = {mtype: [] for mtype in type_keys}
                
                for session in sessions_with_motions:
                    session_motions = motions_queryset.filter(session=session)
                    session_labels.append(session.scheduled_date.strftime('%d.%m.%Y'))
                    
                    for mtype in type_keys:
                        count = session_motions.filter(motion_type=mtype).count()
                        datasets_data[mtype].append(count)
                
                # Prepare chart data structure
                session_chart_datasets = []
                for mtype in type_keys:
                    session_chart_datasets.append({
                        'label': type_labels[mtype],
                        'mtype': mtype,
                        'data': datasets_data[mtype],
                    })
                
                context['session_chart_labels'] = session_labels
                context['session_chart_datasets'] = session_chart_datasets
                context['motion_type_labels'] = type_labels
                
                # Total motions
                context['total_motions'] = motions_queryset.count()
                
                # Recent motions (last 30 days)
                thirty_days_ago = timezone.now() - timedelta(days=30)
                context['recent_motions_count'] = motions_queryset.filter(submitted_date__gte=thirty_days_ago).count()
                
                
            except ImportError:
                # If motion models are not available, set empty stats
                context['motion_status_stats'] = {}
                context['motion_type_stats'] = {}
                context['total_motions'] = 0
                context['recent_motions_count'] = 0
                context['motion_status_chart_data'] = []
                context['session_chart_labels'] = []
                context['session_chart_datasets'] = []
                context['motion_type_labels'] = {}
        else:
            context['motion_status_stats'] = {}
            context['motion_type_stats'] = {}
            context['total_motions'] = 0
            context['recent_motions_count'] = 0
            context['motion_status_chart_data'] = []
            context['session_chart_data'] = []
            context['motion_type_labels'] = {}
        
        return context
    

class DocumentationPageView(TemplateView):
    template_name = "documentation.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['host'] = self.request.get_host()
        return context