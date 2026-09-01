import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import settings
from app.logging_config import get_logger

logger = get_logger("access")


class AccessLogMiddleware(BaseHTTPMiddleware):
    """No-op wiring cost when LOGGING_ENABLED=false (logger is a NullHandler
    at CRITICAL+1 level in that case), so it's safe to leave this installed
    either way."""

    async def dispatch(self, request: Request, call_next):
        if not settings.LOGGING_ENABLED:
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "%s %s -> %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
