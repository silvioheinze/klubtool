import datetime
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, TemplateView, UpdateView, ListView
from django.views.generic.list import ListView
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied

from .forms import CustomUserCreationForm, CustomUserEditForm, RoleForm, RoleFilterForm, CustomAuthenticationForm, LanguageSelectionForm
from .models import Role

CustomUser = get_user_model()


def is_superuser_or_has_permission(permission):
    """Decorator to check if user is superuser or has specific permission"""
    def check_permission(user):
        return user.is_superuser or user.has_role_permission(permission)
    return user_passes_test(check_permission)


class AccountDeleteView(LoginRequiredMixin, DeleteView):
    model = get_user_model()
    template_name = 'user/confirm_delete.html'
    success_url = reverse_lazy('home')

    def get_object(self, queryset=None):
        # Ensure that only the logged-in user can delete their user
        return self.request.user

    def delete(self, request, *args, **kwargs):
        # Optionally, add a message for the user or perform extra cleanup
        messages.success(request, "Your user has been deleted successfully.")
        return super().delete(request, *args, **kwargs)





class SignupPageView(CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy("home")
    template_name = "user/signup.html"

    def form_valid(self, form):
        user = form.instance
        return super().form_valid(form)


def SettingsView(request):
    """
    Display a dashboard overview for the logged-in user.
    If the user is not authenticated, display the login form.
    """
    if request.user.is_authenticated:
        # Handle language change
        language_form = LanguageSelectionForm(request.POST or None, initial={'language': request.user.language})
        
        if request.method == "POST" and 'language' in request.POST:
            if language_form.is_valid():
                new_language = language_form.cleaned_data['language']
                request.user.language = new_language
                request.user.save()
                
                # Set the language in the session
                from django.utils import translation
                translation.activate(new_language)
                request.session['django_language'] = new_language
                
                messages.success(request, f"Language changed to {dict(language_form.fields['language'].choices)[new_language]}")
                return redirect('user-settings')
        
        context = {
            'user': request.user,
            'language_form': language_form,
        }
        return render(request, "user/settings.html", context)
    else:
        # Process the login form for unauthenticated users
        form = CustomAuthenticationForm(request=request, data=request.POST or None)
        if request.method == "POST":
            if form.is_valid():
                user = form.get_user()
                login(request, user)
                return redirect("home")
        return render(request, "user/login.html", {"form": form})


class UsersUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = get_user_model()
    form_class = CustomUserEditForm
    template_name = 'user/edit.html'
    pk_url_kwarg = 'user_id'

    def get_success_url(self):
        return reverse_lazy('user-list')

    def test_func(self):
        # Allow access if user is superuser or has user.edit permission
        return self.request.user.is_superuser or self.request.user.has_role_permission('user.edit')


class UsersListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = get_user_model()
    context_object_name = 'users'
    template_name = 'user/list.html'
    paginate_by = 20

    def test_func(self):
        # Allow access only if user is superuser
        return self.request.user.is_superuser

    def get_queryset(self):
        queryset = CustomUser.objects.select_related('role').prefetch_related(
            'group_memberships__roles'
        ).all().order_by('username')
        
        # Filter by search query
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(username__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query)
            )
        
        # Filter by role
        role_filter = self.request.GET.get('role', '')
        if role_filter:
            queryset = queryset.filter(role__name=role_filter)
        
        # Filter by status
        status_filter = self.request.GET.get('status', '')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['roles'] = Role.objects.filter(is_active=True)
        context['search_query'] = self.request.GET.get('search', '')
        context['role_filter'] = self.request.GET.get('role', '')
        context['status_filter'] = self.request.GET.get('status', '')
        return context


# Role Management Views
class RoleListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Role
    context_object_name = 'roles'
    template_name = 'user/role_list.html'
    paginate_by = 20

    def test_func(self):
        # Allow access only if user is superuser
        return self.request.user.is_superuser

    def get_queryset(self):
        queryset = Role.objects.all().order_by('name')
        
        # Filter by search query
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        # Filter by status
        status_filter = self.request.GET.get('status', '')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['status_filter'] = self.request.GET.get('status', '')
        return context


class RoleCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Role
    form_class = RoleForm
    template_name = 'user/role_form.html'
    success_url = reverse_lazy('role-list')

    def test_func(self):
        # Allow access only if user is superuser
        return self.request.user.is_superuser

    def form_valid(self, form):
        messages.success(self.request, f"Role '{form.instance.name}' created successfully.")
        return super().form_valid(form)


class RoleUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Role
    form_class = RoleForm
    template_name = 'user/role_form.html'
    success_url = reverse_lazy('role-list')

    def test_func(self):
        # Allow access only if user is superuser
        return self.request.user.is_superuser

    def form_valid(self, form):
        messages.success(self.request, f"Role '{form.instance.name}' updated successfully.")
        return super().form_valid(form)


class RoleDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Role
    template_name = 'user/role_confirm_delete.html'
    success_url = reverse_lazy('role-list')

    def test_func(self):
        # Allow access only if user is superuser
        return self.request.user.is_superuser

    def delete(self, request, *args, **kwargs):
        role = self.get_object()
        messages.success(request, f"Role '{role.name}' deleted successfully.")
        return super().delete(request, *args, **kwargs)


@login_required
def user_management_view(request):
    # Allow access only if user is superuser
    if not request.user.is_superuser:
        raise PermissionDenied
    """Comprehensive user management dashboard"""
    User = get_user_model()
    context = {
        'total_users': User.objects.count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'inactive_users': User.objects.filter(is_active=False).count(),
        'users_with_roles': User.objects.filter(role__isnull=False).count(),
        'users_without_roles': User.objects.filter(role__isnull=True).count(),
        'total_roles': Role.objects.count(),
        'active_roles': Role.objects.filter(is_active=True).count(),
        'recent_users': User.objects.prefetch_related('group_memberships__roles').order_by('-date_joined')[:5],
        'recent_roles': Role.objects.order_by('-created_at')[:5],
    }
    return render(request, 'user/management.html', context)
