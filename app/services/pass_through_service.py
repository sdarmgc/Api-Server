"""
Pass-through service.

POST /api/pass-through accepts arbitrary JSON and forwards it verbatim to
the configured backend; whatever the backend returns is sent back verbatim.
No schema is enforced on either side -- request or response can be `{}`,
a list, a deeply nested object, anything valid JSON.

Backend is pluggable via the same registry pattern as the other services
(app/services/semantic_match_service.py, app/services/translation_service.py):
  - "socket" (default, and currently the only registered backend) :
        delegates to an external socket service over TCP (see
        app/services/socket_client.py for the wire protocol). The request
        JSON is sent exactly as received; the response JSON is returned
        exactly as received.

Add further backends by implementing `_run_backend_<name>` and registering
it in `_BACKENDS` below -- the router/circuit-breaker/timeout wiring does
not need to change.
"""
from collections.abc import Callable
from typing import Any

from app.config import settings
from app.logging_config import get_logger
from app.services.circuit_breaker import CircuitBreaker
from app.services.socket_client import call_json_socket_backend

logger = get_logger("pass_through_service")

_breaker = CircuitBreaker(
    name="pass_through_backend",
    fail_max=settings.CIRCUIT_BREAKER_FAIL_MAX,
    reset_timeout_seconds=settings.CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS,
    call_timeout_seconds=settings.BACKEND_CALL_TIMEOUT_SECONDS,
)


async def _run_backend_socket(payload: dict[str, Any]) -> Any:
    return await call_json_socket_backend(
        settings.PASS_THROUGH_BACKEND_HOST,
        settings.PASS_THROUGH_BACKEND_PORT,
        payload,
    )


_BACKENDS: dict[str, Callable[[dict[str, Any]], Any]] = {
    "socket": _run_backend_socket,
}


async def _run_backend(payload: dict[str, Any]) -> Any:
    backend_fn = _BACKENDS.get(settings.PASS_THROUGH_BACKEND)
    if backend_fn is None:
        raise ValueError(f"Unknown PASS_THROUGH_BACKEND '{settings.PASS_THROUGH_BACKEND}'")
    return await backend_fn(payload)


async def pass_through(payload: dict[str, Any]) -> Any:
    logger.info("pass-through request: %d top-level key(s)", len(payload))

    async def call():
        return await _run_backend(payload)

    result = await _breaker.call(call)
    logger.info("pass-through completed")
    return result
