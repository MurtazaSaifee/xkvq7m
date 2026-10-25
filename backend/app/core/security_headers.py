"""Security headers on every response, from a pure ASGI middleware.

The Vercel deployment sets the same headers in vercel.json. This middleware covers the Docker image.
The unexpected-error answer is sent outside the middleware stack, so it sets them itself.
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
    # No full CSP: it could break the ECharts and Vite assets. This only forbids framing.
    "Content-Security-Policy": "frame-ancestors 'none'",
}

_RAW_SECURITY_HEADERS = [
    (name.lower().encode("latin-1"), value.encode("latin-1"))
    for name, value in SECURITY_HEADERS.items()
]


class SecurityHeadersMiddleware:
    """Adds the security headers to every HTTP response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = [*message.get("headers", []), *_RAW_SECURITY_HEADERS]
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
