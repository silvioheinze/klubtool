def group_memberships(request):
    """Context processor to provide group membership data to all templates"""
    context = {
        'user_group_memberships': [],
        'user_locals': [],
        'user_councils': []
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
            
            # Get unique locals and councils from memberships
            locals_from_memberships = set()
            councils_from_memberships = set()
            
            for membership in group_memberships:
                if membership.group.party and membership.group.party.local:
                    locals_from_memberships.add(membership.group.party.local)
                    if hasattr(membership.group.party.local, 'council') and membership.group.party.local.council:
                        councils_from_memberships.add(membership.group.party.local.council)
            
            context['user_locals'] = sorted(locals_from_memberships, key=lambda x: x.name)
            context['user_councils'] = sorted(councils_from_memberships, key=lambda x: x.name)
            
        except ImportError:
            # If models are not available, keep empty lists
            pass
    
    return context
