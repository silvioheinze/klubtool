import datetime
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, TemplateView, UpdateView, ListView
from django.views.generic.list import ListView
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
from django.http import Http404
from allauth.account.views import ConfirmEmailView as AllauthConfirmEmailView
from allauth.account.forms import RequestLoginCodeForm

from user.login_links import consume_magic_link_token
from user.email_verification import ensure_primary_email_address, sync_email_change

from .forms import CustomUserCreationForm, CustomUserEditForm, RoleForm, RoleFilterForm, LanguageSelectionForm, UserSettingsForm, AdminUserCreationForm
from .models import Role, CalendarSubscriptionToken

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

    def get_initial(self):
        initial = super().get_initial()
        email = self.request.GET.get('email', '').strip()
        if email:
            initial['email'] = email
        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        ensure_primary_email_address(
            self.request,
            self.object,
            send_confirmation=True,
            signup=True,
        )
        return response


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
            old_email = request.user.email
            if settings_form.is_valid():
                user = settings_form.save()
                sync_email_change(request, user, old_email)

                # Set the language in the session and activate it immediately
                new_language = settings_form.cleaned_data['language']
                request.session['django_language'] = new_language
                translation.activate(new_language)
                
                # Get the display name for the success message
                language_choices = dict(settings_form.fields['language'].choices)
                language_display = language_choices.get(new_language, new_language)
                
                messages.success(request, f"Settings updated successfully. Language changed to {language_display}")
                return redirect('user-settings')
        
        # Calendar subscription: check if user has active token, and if we have a new URL in session
        has_subscription = CalendarSubscriptionToken.objects.filter(
            user=request.user, is_active=True
        ).exists()
        new_subscription_url = request.session.pop('calendar_subscription_url', None)

        context = {
            'user': request.user,
            'settings_form': settings_form,
            'has_calendar_subscription': has_subscription,
            'new_calendar_subscription_url': new_subscription_url,
        }
        return render(request, "user/settings.html", context)
    else:
        form = RequestLoginCodeForm()
        return render(request, "user/login.html", {"form": form})


def magic_link_login_view(request, token):
    """Log in via a one-time signed magic link from the sign-in email."""
    user_id = consume_magic_link_token(token)
    if user_id is None:
        messages.error(
            request,
            _("This sign-in link is invalid or has expired. Please request a new sign-in email."),
        )
        return redirect('user-settings')

    user = get_object_or_404(CustomUser, pk=user_id, is_active=True)
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')

    next_url = request.GET.get('next') or settings.LOGIN_REDIRECT_URL
    return redirect(next_url)


@login_required
def calendar_subscription_create(request):
    """Create or reset calendar subscription token. Redirects to settings with new URL in session."""
    import secrets
    import hashlib
    from django.urls import reverse
    from .models import CalendarSubscriptionToken
    CalendarSubscriptionToken.objects.filter(user=request.user).update(is_active=False)
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    CalendarSubscriptionToken.objects.create(user=request.user, token_hash=token_hash)
    scheme = 'https' if request.is_secure() else 'http'
    url = f"{scheme}://{request.get_host()}{reverse('calendar-subscription-feed', kwargs={'token': raw_token})}"
    request.session['calendar_subscription_url'] = url
    messages.success(request, _("Your calendar subscription link has been created. Copy it below and add it to your calendar app. If you lose it, use Reset to generate a new one."))
    return redirect('user-settings')


class UsersUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = get_user_model()
    form_class = CustomUserEditForm
    template_name = 'user/edit.html'
    pk_url_kwarg = 'user_id'

    def get_success_url(self):
        return reverse_lazy('user-list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Allow admins to set a new password for the user being edited
        kwargs['allow_set_password'] = (
            self.request.user.is_superuser or self.request.user.has_role_permission('user.edit')
        )
        return kwargs

    def test_func(self):
        # Allow access if user is superuser or has user.edit permission
        return self.request.user.is_superuser or self.request.user.has_role_permission('user.edit')


class UsersListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = get_user_model()
    context_object_name = 'users'
    template_name = 'user/list.html'
    # Server-side pagination (larger page size; use page links to see all users)
    paginate_by = 100

    def test_func(self):
        # Allow access only if user is superuser
        return self.request.user.is_superuser

    def get_queryset(self):
        queryset = CustomUser.objects.select_related('role').prefetch_related(
            'group_memberships__roles',
            'group_memberships__group__party__district',
            'committee_memberships__committee__council__district'
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
                if membership.group.party and membership.group.party.district:
                    locals_set.add(membership.group.party.district)
            # Get locals from committee memberships
            for membership in user.committee_memberships.filter(is_active=True):
                if membership.committee.council and membership.committee.council.district:
                    locals_set.add(membership.committee.council.district)
            user.unique_districts = sorted(locals_set, key=lambda x: x.name)
        
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
        context['email_backend'] = settings.EMAIL_BACKEND.split('.')[-2] if hasattr(settings, 'EMAIL_BACKEND') else 'Not configured'
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
        
        plain_message = render_to_string('user/email/welcome_email.txt', email_context)

        send_mail(
            subject,
            plain_message,
            from_email,
            [target_user.email],
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


@login_required
@require_POST
def user_remove_view(request, user_id):
    """
    Set a user's is_active to False (superusers only). Does not delete the account.
    """
    if not request.user.is_superuser:
        raise PermissionDenied
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        raise PermissionDenied
    if uid == request.user.pk:
        messages.error(request, _("You cannot remove your own account."))
        return redirect('user-list')
    target = get_object_or_404(CustomUser, pk=uid)
    if not target.is_active:
        messages.info(request, _("This user is already inactive."))
        return redirect('user-list')
    target.is_active = False
    target.save(update_fields=['is_active'])
    messages.success(
        request,
        _("User %(username)s has been removed. They can no longer log in.")
        % {'username': target.username},
    )
    return redirect('user-list')


@login_required
@require_POST
def resend_email_verification(request):
    """Send another verification email for the current user's primary address."""
    email = request.user.email
    if not email:
        messages.error(request, _("Your account does not have an email address configured."))
        return redirect('home')

    email_address = ensure_primary_email_address(request, request.user, send_confirmation=False)
    if email_address.verified:
        messages.info(request, _("Your email is already verified."))
        return redirect('home')

    from allauth.account.internal.flows.email_verification import send_verification_email_to_address
    send_verification_email_to_address(request, email_address, signup=False)
    return redirect('account_email_verification_sent')


class CustomConfirmEmailView(AllauthConfirmEmailView):
    """Custom email confirmation view with Bootstrap template and user feedback."""
    template_name = "account/email_confirm.html"

    def post(self, *args, **kwargs):
        try:
            confirmation = self.get_object()
            email_address = confirmation.email_address
            user_to_confirm = email_address.user
        except Http404:
            email_address = None
            user_to_confirm = None

        prior_user_pk = self.request.user.pk if self.request.user.is_authenticated else None
        response = super().post(*args, **kwargs)

        if email_address is not None:
            email_address.refresh_from_db()
            if email_address.verified:
                if prior_user_pk != user_to_confirm.pk:
                    if prior_user_pk is not None:
                        from django.contrib.auth import logout
                        logout(self.request)
                    login(
                        self.request,
                        user_to_confirm,
                        backend='django.contrib.auth.backends.ModelBackend',
                    )
                    messages.success(
                        self.request,
                        _("Your email has been confirmed and you have been logged in."),
                    )
                else:
                    messages.success(self.request, _("Your email has been confirmed."))

        return response
