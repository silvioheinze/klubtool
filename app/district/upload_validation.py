"""Validation helpers for token-based attachment uploads."""

import os
import re

ALLOWED_ATTACHMENT_EXTENSIONS = (
    '.pdf',
    '.doc',
    '.docx',
    '.txt',
    '.jpg',
    '.jpeg',
    '.png',
    '.gif',
    '.xls',
    '.xlsx',
    '.ppt',
    '.pptx',
)

UPLOAD_PUT_MAX_BYTES = 25 * 1024 * 1024
UPLOAD_TOKEN_TTL_SECONDS = 600
UPLOAD_DESCRIPTION_MAX_LENGTH = 500

_UNSAFE_FILENAME = re.compile(r'[/\\|\x00]')


def normalize_upload_filename(filename: str) -> str:
    """Return basename only; reject path segments and empty names."""
    if not filename or not str(filename).strip():
        raise ValueError('filename is required.')
    base = os.path.basename(str(filename).strip())
    if not base or base in ('.', '..') or _UNSAFE_FILENAME.search(base):
        raise ValueError('Invalid filename.')
    return base


def extension_for_filename(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def validate_upload_extension(filename: str) -> None:
    ext = extension_for_filename(filename)
    if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
        allowed = ', '.join(ALLOWED_ATTACHMENT_EXTENSIONS)
        raise ValueError(f'File type not allowed. Allowed types: {allowed}')


def content_matches_extension(ext: str, head: bytes) -> bool:
    """Rough magic-byte check for the declared extension."""
    if not head and ext == '.txt':
        return True
    if ext == '.pdf':
        return head.startswith(b'%PDF')
    if ext in ('.jpg', '.jpeg'):
        return len(head) >= 3 and head[:3] == b'\xff\xd8\xff'
    if ext == '.png':
        return head.startswith(b'\x89PNG\r\n\x1a\n')
    if ext == '.gif':
        return head.startswith(b'GIF87a') or head.startswith(b'GIF89a')
    if ext in ('.doc', '.xls', '.ppt'):
        return head.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1')
    if ext in ('.docx', '.xlsx', '.pptx'):
        return head.startswith(b'PK')
    if ext == '.txt':
        return b'\x00' not in head[:8192]
    return False
