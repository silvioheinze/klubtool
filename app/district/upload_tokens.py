"""Signed one-time upload URLs for attachment PUT endpoint."""

import secrets

from django.conf import settings
from django.core.cache import caches
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.urls import reverse

from district.upload_validation import (
    UPLOAD_DESCRIPTION_MAX_LENGTH,
    UPLOAD_PUT_MAX_BYTES,
    UPLOAD_TOKEN_TTL_SECONDS,
    normalize_upload_filename,
    validate_upload_extension,
)

SIGNER_SALT = 'district.attachment_upload'
CACHE_ALIAS = 'upload_tokens'
CACHE_KEY_PREFIX = 'upload_jti:'


def _upload_token_cache():
    return caches[CACHE_ALIAS]


def _signer() -> TimestampSigner:
    return TimestampSigner(salt=SIGNER_SALT)


def _token_timeout() -> int:
    return getattr(settings, 'ATTACHMENT_UPLOAD_TOKEN_TTL', UPLOAD_TOKEN_TTL_SECONDS)


def build_committee_meeting_upload_payload(
    *,
    committee_meeting_id: int,
    user_id: int,
    filename: str,
    file_type: str,
    description: str = '',
) -> dict:
    safe_name = normalize_upload_filename(filename)
    validate_upload_extension(safe_name)
    desc = (description or '')[:UPLOAD_DESCRIPTION_MAX_LENGTH]
    return {
        'parent': 'committee_meeting',
        'parent_id': committee_meeting_id,
        'user_id': user_id,
        'filename': safe_name,
        'file_type': file_type,
        'description': desc,
        'jti': secrets.token_urlsafe(16),
    }


def build_session_upload_payload(
    *,
    session_id: int,
    user_id: int,
    filename: str,
    file_type: str,
    description: str = '',
) -> dict:
    safe_name = normalize_upload_filename(filename)
    validate_upload_extension(safe_name)
    desc = (description or '')[:UPLOAD_DESCRIPTION_MAX_LENGTH]
    return {
        'parent': 'session',
        'parent_id': session_id,
        'user_id': user_id,
        'filename': safe_name,
        'file_type': file_type,
        'description': desc,
        'jti': secrets.token_urlsafe(16),
    }


def build_motion_upload_payload(
    *,
    motion_id: int,
    user_id: int,
    filename: str,
    file_type: str,
    description: str = '',
) -> dict:
    safe_name = normalize_upload_filename(filename)
    validate_upload_extension(safe_name)
    desc = (description or '')[:UPLOAD_DESCRIPTION_MAX_LENGTH]
    return {
        'parent': 'motion',
        'parent_id': motion_id,
        'user_id': user_id,
        'filename': safe_name,
        'file_type': file_type,
        'description': desc,
        'jti': secrets.token_urlsafe(16),
    }


def build_inquiry_upload_payload(
    *,
    inquiry_id: int,
    user_id: int,
    filename: str,
    file_type: str,
    description: str = '',
) -> dict:
    safe_name = normalize_upload_filename(filename)
    validate_upload_extension(safe_name)
    desc = (description or '')[:UPLOAD_DESCRIPTION_MAX_LENGTH]
    return {
        'parent': 'inquiry',
        'parent_id': inquiry_id,
        'user_id': user_id,
        'filename': safe_name,
        'file_type': file_type,
        'description': desc,
        'jti': secrets.token_urlsafe(16),
    }


def build_district_event_upload_payload(
    *,
    event_id: int,
    user_id: int,
    filename: str,
    file_type: str,
    description: str = '',
) -> dict:
    safe_name = normalize_upload_filename(filename)
    validate_upload_extension(safe_name)
    desc = (description or '')[:UPLOAD_DESCRIPTION_MAX_LENGTH]
    return {
        'parent': 'district_event',
        'parent_id': event_id,
        'user_id': user_id,
        'filename': safe_name,
        'file_type': file_type,
        'description': desc,
        'jti': secrets.token_urlsafe(16),
    }


def mint_upload_token(payload: dict) -> str:
    return _signer().sign_object(payload)


def verify_upload_token(token: str) -> dict | None:
    try:
        return _signer().unsign_object(token, max_age=_token_timeout())
    except (BadSignature, SignatureExpired):
        return None


def consume_upload_jti(jti: str) -> bool:
    """
    Atomically mark a token as used.

    Returns True if this call consumed the jti; False if already used.
    """
    cache = _upload_token_cache()
    key = f'{CACHE_KEY_PREFIX}{jti}'
    return cache.add(key, 1, timeout=_token_timeout())


def build_attachment_upload_url(request, payload: dict) -> str:
    """Return an absolute HTTPS upload URL.

    The app sits behind a reverse proxy that terminates TLS, so the incoming
    request is HTTP. MCP clients always reach the public host over HTTPS, the
    same way the MCP server URL in settings is built.
    """
    signed = mint_upload_token(payload)
    path = reverse('attachment-upload', kwargs={'token': signed})
    return f'https://{request.get_host()}{path}'


def upload_url_response_fields(*, max_bytes: int | None = None) -> dict:
    return {
        'expires_in': _token_timeout(),
        'method': 'PUT',
        'max_bytes': UPLOAD_PUT_MAX_BYTES if max_bytes is None else max_bytes,
    }
