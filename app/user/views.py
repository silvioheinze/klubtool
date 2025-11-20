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
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

from .forms import CustomUserCreationForm, CustomUserEditForm, RoleForm, RoleFilterForm, CustomAuthenticationForm, LanguageSelectionForm, UserSettingsForm, AdminUserCreationForm
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
        # Ensure the user's language preference is active
        from django.utils import translation
        user_language = getattr(request.user, 'language', 'de')
        translation.activate(user_language)
        request.session['django_language'] = user_language
        
        # Handle settings form submission
        settings_form = UserSettingsForm(request.POST or None, instance=request.user)
        
        if request.method == "POST":
            if settings_form.is_valid():
                # Update user's settings
                settings_form.save()
                
                # Set the language in the session and activate it immediately
                new_language = settings_form.cleaned_data['language']
                request.session['django_language'] = new_language
                translation.activate(new_language)
                
                # Get the display name for the success message
                language_choices = dict(settings_form.fields['language'].choices)
                language_display = language_choices.get(new_language, new_language)
                
                messages.success(request, f"Settings updated successfully. Language changed to {language_display}")
                return redirect('user-settings')
        
        context = {
            'user': request.user,
            'settings_form': settings_form,
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
            'group_memberships__roles',
            'group_memberships__group__party__local',
            'committee_memberships__committee__council__local'
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
        
        # Pre-calculate unique locals for each user to avoid template complexity
        for user in context['users']:
            locals_set = set()
            # Get locals from group memberships
            for membership in user.group_memberships.filter(is_active=True):
                if membership.group.party and membership.group.party.local:
                    locals_set.add(membership.group.party.local)
            # Get locals from committee memberships
            for membership in user.committee_memberships.filter(is_active=True):
                if membership.committee.council and membership.committee.council.local:
                    locals_set.add(membership.committee.council.local)
            user.unique_locals = sorted(locals_set, key=lambda x: x.name)
        
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




class AdminUserCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating users administratively (bypassing normal registration)"""
    model = CustomUser
    form_class = AdminUserCreationForm
    template_name = 'user/admin_user_form.html'
    success_url = reverse_lazy('user-list')

    def test_func(self):
        """Check if user has permission to create users administratively"""
        return self.request.user.is_superuser

    def form_valid(self, form):
        """Display success message and handle user creation"""
        user = form.save()
        messages.success(
            self.request, 
            f"User '{user.username}' created successfully. "
            f"The user will need to set their password on first login."
        )
        return super().form_valid(form)


class AdminSettingsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """View for admin settings including test email functionality"""
    template_name = 'user/admin_settings.html'

    def test_func(self):
        """Check if user is superuser"""
        return self.request.user.is_superuser

    def post(self, request, *args, **kwargs):
        """Handle POST request for sending test email"""
        if 'send_test_email' in request.POST:
            user = request.user
            if not user.email:
                messages.error(request, _("Your account doesn't have an email address configured. Please add an email address in your settings first."))
                return redirect('admin-settings')
            
            try:
                # Send test email
                subject = _("Test Email from Klubtool")
                message = _(
                    "This is a test email from Klubtool.\n\n"
                    "If you received this email, your email configuration is working correctly.\n\n"
                    "Sent to: {email}\n"
                    "User: {username}\n"
                    "Time: {time}"
                ).format(
                    email=user.email,
                    username=user.username,
                    time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                
                from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@klubtool.local')
                send_mail(
                    subject,
                    message,
                    from_email,
                    [user.email],
                    fail_silently=False,
                )
                messages.success(request, _("Test email sent successfully to {email}").format(email=user.email))
            except Exception as e:
                messages.error(request, _("Failed to send test email: {error}").format(error=str(e)))
            
            return redirect('admin-settings')
        
        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        # Add email backend info for display
        context['email_backend'] = settings.EMAIL_BACKEND.split('.')[-1] if hasattr(settings, 'EMAIL_BACKEND') else 'Not configured'
        return context


@login_required
@user_passes_test(lambda u: u.is_superuser)
def send_welcome_email(request, user_id):
    """Send welcome email to a user (only for users who haven't logged in yet)"""
    target_user = get_object_or_404(CustomUser, pk=user_id)
    
    if not target_user.email:
        messages.error(request, _("User {username} doesn't have an email address configured.").format(username=target_user.username))
        return redirect('user-list')
    
    # Check if user has already logged in
    if target_user.last_login is not None:
        messages.warning(request, _("User {username} has already logged in. Welcome emails can only be sent to users who haven't logged in yet.").format(username=target_user.username))
        return redirect('user-list')
    
    try:
        # Prepare email content
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@klubtool.local')
        subject = _("Welcome to Klubtool")
        
        # Render email template
        email_context = {
            'user': target_user,
            'site_url': request.build_absolute_uri('/'),
        }
        
        # Try to render HTML email first, fallback to plain text
        try:
            html_message = render_to_string('user/email/welcome_email.html', email_context)
            plain_message = render_to_string('user/email/welcome_email.txt', email_context)
        except:
            # Fallback to plain text if HTML template doesn't exist
            plain_message = render_to_string('user/email/welcome_email.txt', email_context)
            html_message = None
        
        send_mail(
            subject,
            plain_message,
            from_email,
            [target_user.email],
            html_message=html_message,
            fail_silently=False,
        )
        messages.success(
            request, 
            _("Welcome email sent successfully to {email}").format(email=target_user.email)
        )
    except Exception as e:
        messages.error(request, _("Failed to send welcome email: {error}").format(error=str(e)))
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send welcome email to {target_user.email}: {str(e)}")
    
    return redirect('user-list')
