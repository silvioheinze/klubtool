from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.db.models import Q
from django.contrib.auth import get_user_model
from .models import Group, GroupMember
from .forms import GroupForm, GroupFilterForm, GroupMemberForm, GroupMemberFilterForm

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
    success_url = reverse_lazy('group:member-list')

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
