"""
Semantic match service.

Backend is pluggable via SEMANTIC_MATCHING_BACKEND, mirroring the same
registry pattern used by the translation service
(app/services/translation_service.py):

  - "socket" (default, and currently the only registered backend) :
        delegates to an external socket service over TCP (see
        app/services/socket_client.py for the wire protocol).
        Request/response use exactly the same JSON structure as this
        endpoint's own HTTP contract -- {"targets": [...], "corpus":
        [...], "score": ...} in.

The response is intentionally *not* validated against a fixed schema --
whatever JSON the backend returns is passed straight through to the
caller as-is (including something as minimal as `{}`). This keeps the API
from being tightly coupled to one particular backend's response shape;
see app/routers/semantic_match.py's `response_model=Any` for the other
half of this.

This module ships with no built-in matching algorithm -- it's purely the
pluggable-backend wiring (registry + circuit breaker/timeout). The TF-IDF
+ cosine-similarity reference implementation used to answer socket calls
during local dev/testing lives in scripts/mock_semantic_match_backend.py,
not here, so it's clear that's a stand-in for a real backend rather than
part of the production service.

Add further backends by implementing `_run_backend_<name>` and registering
it in `_BACKENDS` below -- the router/circuit-breaker/timeout wiring does
not need to change.
"""
from collections.abc import Callable
from typing import Any

from app.config import settings
from app.logging_config import get_logger
from app.schemas.semantic_match import SemanticMatchRequest
from app.services.circuit_breaker import CircuitBreaker
from app.services.socket_client import call_json_socket_backend

logger = get_logger("semantic_match_service")

_breaker = CircuitBreaker(
    name="semantic_match_backend",
    fail_max=settings.CIRCUIT_BREAKER_FAIL_MAX,
    reset_timeout_seconds=settings.CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS,
    call_timeout_seconds=settings.BACKEND_CALL_TIMEOUT_SECONDS,
)


async def _run_backend_socket(targets: list[str], corpus: list[str], min_score: float) -> Any:
    request_payload = {"targets": targets, "corpus": corpus, "score": min_score}
    # Returned as-is -- no schema/shape enforced on the response. Could be
    # a list of match objects, an empty list, an empty object `{}`, or
    # anything else valid JSON the backend chooses to send back.
    return await call_json_socket_backend(
        settings.SEMANTIC_MATCHING_BACKEND_HOST,
        settings.SEMANTIC_MATCHING_BACKEND_PORT,
        request_payload,
    )


_BACKENDS: dict[str, Callable[[list[str], list[str], float], Any]] = {
    "socket": _run_backend_socket,
}


async def _run_backend(targets: list[str], corpus: list[str], min_score: float) -> Any:
    backend_fn = _BACKENDS.get(settings.SEMANTIC_MATCHING_BACKEND)
    if backend_fn is None:
        raise ValueError(
            f"Unknown SEMANTIC_MATCHING_BACKEND '{settings.SEMANTIC_MATCHING_BACKEND}'"
        )
    return await backend_fn(targets, corpus, min_score)


async def match(request: SemanticMatchRequest) -> Any:
    logger.info(
        "semantic-match request: %d target(s) vs %d corpus item(s), min_score=%s",
        len(request.targets),
        len(request.corpus),
        request.score,
    )

    async def call():
        return await _run_backend(request.targets, request.corpus, request.score)

    result = await _breaker.call(call)
    logger.info("semantic-match completed")
    return result
