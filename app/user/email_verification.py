"""Helpers for keeping allauth EmailAddress records in sync with CustomUser."""

from allauth.account.internal.flows.email_verification import send_verification_email_to_address
from allauth.account.models import EmailAddress


def ensure_primary_email_address(request, user, *, send_confirmation=False, signup=False):
    """
    Ensure the user has a primary EmailAddress matching user.email.

    Optionally send a verification email for new or unverified addresses.
    """
    email = (user.email or '').lower()
    if not email:
        return None

    email_address, created = EmailAddress.objects.get_or_create(
        user=user,
        email=email,
        defaults={'primary': True, 'verified': False},
    )
    if not created:
        updated_fields = []
        if not email_address.primary:
            EmailAddress.objects.filter(user=user).exclude(pk=email_address.pk).update(primary=False)
            email_address.primary = True
            updated_fields.append('primary')
        if send_confirmation and email_address.verified:
            email_address.verified = False
            updated_fields.append('verified')
        if updated_fields:
            email_address.save(update_fields=updated_fields)
    else:
        EmailAddress.objects.filter(user=user).exclude(pk=email_address.pk).update(primary=False)

    if send_confirmation and not email_address.verified:
        send_verification_email_to_address(request, email_address, signup=signup)

    return email_address


def sync_email_change(request, user, old_email):
    """Replace the primary email address when the user changes their email."""
    new_email = (user.email or '').lower()
    old_email = (old_email or '').lower()
    if not new_email or new_email == old_email:
        return None

    EmailAddress.objects.filter(user=user).exclude(email=new_email).delete()

    return ensure_primary_email_address(
        request,
        user,
        send_confirmation=True,
        signup=False,
    )
