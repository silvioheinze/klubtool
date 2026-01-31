"""
Logging filters to suppress or downgrade expected application errors
so they don't clutter logs with WARNING tracebacks (e.g. PermissionDenied).
"""

import logging

try:
    from django.core.exceptions import PermissionDenied
except ImportError:
    PermissionDenied = None


class SuppressExpectedRequestErrors(logging.Filter):
    """
    Filter out log records for expected HTTP client errors that are handled
    by Django (403 Permission Denied). These are normal outcomes (e.g. tests
    or users hitting forbidden URLs) and need not be logged as WARNING with
    full traceback.
    """

    def filter(self, record):
        if record.exc_info:
            exc_type, exc_value, _ = record.exc_info
            if exc_value is not None and PermissionDenied is not None:
                if isinstance(exc_value, PermissionDenied):
                    return False
        msg = record.getMessage()
        if "Forbidden (Permission denied)" in msg:
            return False
        # Suppress form validation error logs (expected during tests / invalid input)
        if "Form errors:" in msg or "Form validation failed" in msg or "Form has " in msg and " error fields" in msg:
            return False
        if "Vote form " in msg and " errors:" in msg:
            return False
        return True
