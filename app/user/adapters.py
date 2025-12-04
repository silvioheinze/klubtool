from allauth.account.adapter import DefaultAccountAdapter
from django.contrib.auth import login
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.utils.translation import gettext_lazy as _


class CustomAccountAdapter(DefaultAccountAdapter):
    """Custom account adapter to keep users logged in after email confirmation"""
    
    def confirm_email(self, request, email_address):
        """Override to log the user in after email confirmation"""
        # Call the parent method to confirm the email
        super().confirm_email(request, email_address)
        
        # Log the user in if they're not already logged in
        # Note: ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION setting should handle this,
        # but we ensure it here as well
        if not request.user.is_authenticated:
            user = email_address.user
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        
        return email_address
    
    def is_open_for_signup(self, request):
        """Allow signups"""
        return True
    
    def get_email_verification_redirect_url(self, email_address):
        """Return the URL to redirect to after email verification"""
        # Redirect to home page after confirmation, user will be logged in
        from django.urls import reverse
        return reverse('home')

