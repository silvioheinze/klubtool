"""JSON-RPC MCP HTTP endpoint."""

import json

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from mcp.auth import authenticate_mcp_request
from mcp.tools import McpToolError, call_tool, list_tools, tool_result_content

MCP_PROTOCOL_VERSION = '2024-11-05'
SERVER_NAME = 'klubtool'
SERVER_VERSION = '1.0.0'
UNAUTHORIZED_CODE = -32001


def _json_rpc_error(request_id, code, message):
    return {
        'jsonrpc': '2.0',
        'id': request_id,
        'error': {'code': code, 'message': message},
    }


def _json_rpc_result(request_id, result):
    return {
        'jsonrpc': '2.0',
        'id': request_id,
        'result': result,
    }


def _parse_body(request):
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, _json_rpc_error(None, -32700, 'Parse error')

    if isinstance(payload, list):
        if len(payload) != 1:
            return None, _json_rpc_error(None, -32600, 'Batch requests are not supported')
        payload = payload[0]

    if not isinstance(payload, dict):
        return None, _json_rpc_error(None, -32600, 'Invalid Request')

    return payload, None


def _handle_method(method, params, request, user):
    if method == 'initialize':
        return {
            'protocolVersion': MCP_PROTOCOL_VERSION,
            'capabilities': {'tools': {}},
            'serverInfo': {'name': SERVER_NAME, 'version': SERVER_VERSION},
        }

    if method == 'ping':
        return {}

    if method == 'tools/list':
        return {'tools': list_tools()}

    if method == 'tools/call':
        tool_name = (params or {}).get('name')
        arguments = (params or {}).get('arguments') or {}
        if not tool_name:
            raise McpToolError('Missing tool name.')
        try:
            result = call_tool(tool_name, arguments, user, request=request)
            return tool_result_content(result, is_error=False)
        except McpToolError as exc:
            return tool_result_content({'error': str(exc)}, is_error=True)

    raise McpToolError(f'Method not found: {method}')


@csrf_exempt
@require_http_methods(['GET', 'POST', 'DELETE'])
def mcp_endpoint(request):
    """
    MCP Streamable HTTP endpoint (JSON responses).

    All tool methods require Authorization: Bearer <McpToken>.
    initialize also requires auth so clients must configure the token up front.
    """
    if request.method == 'GET':
        return JsonResponse({'name': SERVER_NAME, 'version': SERVER_VERSION, 'mcp': True})

    if request.method == 'DELETE':
        return HttpResponse(status=405)

    payload, error_response = _parse_body(request)
    if error_response is not None:
        return JsonResponse(error_response, status=400)

    request_id = payload.get('id')
    method = payload.get('method')
    params = payload.get('params') or {}

    if method == 'notifications/initialized':
        return HttpResponse(status=202)

    user = authenticate_mcp_request(request)
    if user is None:
        return JsonResponse(
            _json_rpc_error(request_id, UNAUTHORIZED_CODE, 'Unauthorized'),
            status=401,
        )

    try:
        if method in ('initialize', 'ping', 'tools/list', 'tools/call'):
            result = _handle_method(method, params, request, user)
            return JsonResponse(_json_rpc_result(request_id, result))
        return JsonResponse(
            _json_rpc_error(request_id, -32601, f'Method not found: {method}'),
            status=404,
        )
    except McpToolError as exc:
        return JsonResponse(
            _json_rpc_error(request_id, -32602, str(exc)),
            status=400,
        )
    except Exception as exc:
        return JsonResponse(
            _json_rpc_error(request_id, -32603, 'Internal error'),
            status=500,
        )
