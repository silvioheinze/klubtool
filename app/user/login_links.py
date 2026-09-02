"""One-time magic-link tokens for cross-device passwordless login."""

import secrets

from django.conf import settings
from django.core.cache import cache
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.urls import reverse

CACHE_PREFIX = 'login_magic_link:'


def _timeout() -> int:
    return getattr(settings, 'ACCOUNT_LOGIN_BY_CODE_TIMEOUT', 600)


def create_magic_link_url(request, user) -> str:
    """Mint a signed, one-time magic link for the given user."""
    nonce = secrets.token_urlsafe(32)
    signer = TimestampSigner(salt='user.login_magic_link')
    token = signer.sign(f'{user.pk}:{nonce}')
    cache_key = f'{CACHE_PREFIX}{nonce}'
    cache.set(cache_key, user.pk, timeout=_timeout())
    return request.build_absolute_uri(
        reverse('user-login-link', kwargs={'token': token})
    )


def consume_magic_link_token(token: str) -> int | None:
    """
    Validate and consume a magic-link token.

    Returns the user pk on success, or None if invalid, expired, or reused.
    """
    signer = TimestampSigner(salt='user.login_magic_link')
    try:
        value = signer.unsign(token, max_age=_timeout())
    except (BadSignature, SignatureExpired):
        return None

    try:
        user_id_str, nonce = value.split(':', 1)
    except ValueError:
        return None

    cache_key = f'{CACHE_PREFIX}{nonce}'
    cached_user_id = cache.get(cache_key)
    if cached_user_id is None or str(cached_user_id) != user_id_str:
        return None

    cache.delete(cache_key)
    return int(user_id_str)
