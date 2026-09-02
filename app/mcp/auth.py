"""Bearer token authentication for MCP requests."""

from user.models import McpToken


def authenticate_mcp_request(request):
    """
    Resolve the Klubtool user from Authorization: Bearer <token>.

    Returns the user on success, or None if the token is missing/invalid or the user is inactive.
    """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth_header.startswith('Bearer '):
        return None

    raw_token = auth_header[7:].strip()
    if not raw_token:
        return None

    token = McpToken.lookup(raw_token)
    if token is None:
        return None

    user = token.user
    if not user.is_active:
        return None

    token.update_last_used()
    return user
