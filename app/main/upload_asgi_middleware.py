"""ASGI middleware: reject oversized PUT uploads before Django handles the body."""

from district.upload_validation import UPLOAD_PUT_MAX_BYTES


class UploadSizeLimitMiddleware:
    """Require Content-Length and cap declared size on attachment upload path."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get('type') != 'http':
            await self.app(scope, receive, send)
            return

        path = scope.get('path', '')
        method = scope.get('method', '').upper()
        if method != 'PUT' or not path.startswith('/uploads/attachments/'):
            await self.app(scope, receive, send)
            return

        headers = {k.decode().lower(): v.decode() for k, v in scope.get('headers', [])}
        content_length = headers.get('content-length')
        if content_length is None:
            await self._send_simple(send, 411)
            return
        try:
            declared = int(content_length)
        except ValueError:
            await self._send_simple(send, 400)
            return
        if declared < 0 or declared > UPLOAD_PUT_MAX_BYTES:
            await self._send_simple(send, 413)
            return

        await self.app(scope, receive, send)

    @staticmethod
    async def _send_simple(send, status: int):
        await send(
            {
                'type': 'http.response.start',
                'status': status,
                'headers': [(b'content-length', b'0')],
            }
        )
        await send({'type': 'http.response.body', 'body': b''})
