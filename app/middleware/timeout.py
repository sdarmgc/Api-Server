"""
Hard ceiling on total request processing time. This is a second, outer
layer of defense on top of the per-backend-call timeouts enforced by the
CircuitBreaker (app/services/circuit_breaker.py) -- it catches the case
where a handler does several small calls that each individually pass their
own timeout but collectively still take too long.
"""
import asyncio

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings
from app.logging_config import get_logger

logger = get_logger("timeout_middleware")


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await asyncio.wait_for(
                call_next(request), timeout=settings.REQUEST_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Request timed out after %.1fs: %s %s",
                settings.REQUEST_TIMEOUT_SECONDS,
                request.method,
                request.url.path,
            )
            return JSONResponse(
                status_code=504,
                content={
                    "detail": (
                        f"Request exceeded the {settings.REQUEST_TIMEOUT_SECONDS}s "
                        "timeout."
                    )
                },
            )
