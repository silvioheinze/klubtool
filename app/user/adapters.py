from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.utils import filter_users_by_email

from user.login_links import create_magic_link_url


class CustomAccountAdapter(DefaultAccountAdapter):
    """Custom account adapter for redirects and login-code emails."""

    def is_open_for_signup(self, request):
        """Allow signups"""
        return True
    
    def get_email_verification_redirect_url(self, email_address):
        """Return the URL to redirect to after email verification"""
        # Redirect to home page after confirmation, user will be logged in
        from django.urls import reverse
        return reverse('home')

    def send_mail(self, template_prefix, email, context):
        """Add a cross-device magic link to login-code emails."""
        if template_prefix == 'account/email/login_code':
            request = context.get('request')
            users = filter_users_by_email(email, is_active=True)
            if request and users:
                context = {**context, 'magic_link': create_magic_link_url(request, users[0])}
        return super().send_mail(template_prefix, email, context)

