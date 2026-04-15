"""Request-Logging Middleware."""

import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("api.requests")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)
        # Nur API-Requests loggen (nicht Health-Checks)
        if request.url.path.startswith("/api") and request.url.path != "/health":
            logger.info(
                f"{request.method} {request.url.path} → {response.status_code} ({duration_ms}ms)"
            )
        return response
