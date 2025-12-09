def group_memberships(request):
    """Context processor to provide group membership data to all templates"""
    context = {
        'user_group_memberships': [],
        'user_locals': [],
        'user_councils': [],
        'user_group_admin_groups': [],
        'user_leader_groups': [],
        'next_session': None,
        'next_group_meeting': None
    }
    
    if request.user.is_authenticated:
        try:
            from group.models import GroupMember
            from local.models import Local, Council
            
            # Get user's group memberships
            group_memberships = GroupMember.objects.filter(
                user=request.user,
                is_active=True
            ).select_related(
                'group',
                'group__party',
                'group__party__local'
            ).order_by('group__name')
            
            context['user_group_memberships'] = group_memberships
            
            # Get user's group admin groups
            group_admin_groups = GroupMember.objects.filter(
                user=request.user,
                roles__name='Group Admin',
                is_active=True
            ).select_related(
                'group',
                'group__party',
                'group__party__local'
            ).order_by('group__name')
            
            context['user_group_admin_groups'] = group_admin_groups
            
            # Get user's leader groups (Leader or Deputy Leader roles)
            leader_groups = GroupMember.objects.filter(
                user=request.user,
                roles__name__in=['Leader', 'Deputy Leader'],
                is_active=True
            ).select_related(
                'group',
                'group__party',
                'group__party__local'
            ).order_by('group__name')
            
            context['user_leader_groups'] = leader_groups
            
            # Create a combined, deduplicated list of all groups the user belongs to
            # (combining leader groups and admin groups, removing duplicates)
            seen_group_ids = set()
            combined_groups = []
            
            # Add leader groups first
            for membership in leader_groups:
                if membership.group.pk not in seen_group_ids:
                    seen_group_ids.add(membership.group.pk)
                    combined_groups.append(membership)
            
            # Add admin groups (skip if already added as leader)
            for membership in group_admin_groups:
                if membership.group.pk not in seen_group_ids:
                    seen_group_ids.add(membership.group.pk)
                    combined_groups.append(membership)
            
            context['user_all_groups'] = combined_groups
            
            # Get unique locals and councils from memberships
            locals_from_memberships = set()
            councils_from_memberships = set()
            
            for membership in group_memberships:
                if membership.group.party and membership.group.party.local:
                    locals_from_memberships.add(membership.group.party.local)
                    if hasattr(membership.group.party.local, 'council') and membership.group.party.local.council:
                        councils_from_memberships.add(membership.group.party.local.council)
            
            # For superusers, show all councils
            if request.user.is_superuser:
                from local.models import Council
                all_councils = Council.objects.filter(is_active=True)
                councils_from_memberships.update(all_councils)
                for council in all_councils:
                    if council.local:
                        locals_from_memberships.add(council.local)
            
            context['user_locals'] = sorted(locals_from_memberships, key=lambda x: x.name)
            context['user_councils'] = sorted(councils_from_memberships, key=lambda x: x.name)
            
            # Get next session within 14 days for user's councils
            from django.utils import timezone
            from datetime import timedelta
            
            now = timezone.now()
            fourteen_days_from_now = now + timedelta(days=14)
            
            # Get sessions for user's councils that are within 14 days
            if councils_from_memberships:
                from local.models import Session
                next_session = Session.objects.filter(
                    council__in=councils_from_memberships,
                    scheduled_date__gte=now.date(),
                    scheduled_date__lte=fourteen_days_from_now.date(),
                    is_active=True
                ).order_by('scheduled_date').first()
                
                context['next_session'] = next_session
            
            # Get next group meeting within 14 days for user's groups
            if combined_groups:
                from group.models import GroupMeeting
                user_group_ids = [membership.group.pk for membership in combined_groups]
                next_group_meeting = GroupMeeting.objects.filter(
                    group__pk__in=user_group_ids,
                    scheduled_date__gte=now,
                    scheduled_date__lte=fourteen_days_from_now,
                    is_active=True
                ).select_related('group').order_by('scheduled_date').first()
                
                context['next_group_meeting'] = next_group_meeting
            
        except ImportError:
            # If models are not available, keep empty lists
            pass
    
    return context
