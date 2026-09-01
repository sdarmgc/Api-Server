"""
Translation service.

The real translation backend is being provided separately and will be
wired in over the socket protocol below -- only a "mock" stand-in is
included here for local dev and the test suite.

Backend is pluggable via TRANSLATION_BACKEND:
  - "socket" (default) : delegates to an external socket service over TCP
                          (see app/services/socket_client.py for the wire
                          protocol). Request/response use exactly the same
                          JSON structure as this endpoint's own HTTP
                          contract -- {"source-text": [...], "source-lang":
                          ..., "target-lang": ..., "option": ...} in, the
                          same shape (plus "target-text") out. Point
                          TRANSLATION_BACKEND_HOST/_PORT at the real
                          backend once it's ready.
  - "mock"              : deterministic, fully offline placeholder. Wraps
                           each string as "[<target-lang>] <source text>"
                           so callers can see the plumbing works
                           end-to-end. Used by the test suite
                           (tests/conftest.py starts
                           scripts/mock_translate_backend.py, which
                           implements this same logic over a real socket).

Add further backends by implementing `_translate_<name>` and registering it
in `_BACKENDS` below -- the router/circuit-breaker/timeout wiring does not
need to change.
"""
from collections.abc import Callable

from app.config import settings
from app.logging_config import get_logger
from app.schemas.translate import TranslateRequest, TranslateResponse
from app.services.circuit_breaker import CircuitBreaker
from app.services.socket_client import call_json_socket_backend

logger = get_logger("translation_service")

_breaker = CircuitBreaker(
    name="translation_backend",
    fail_max=settings.CIRCUIT_BREAKER_FAIL_MAX,
    reset_timeout_seconds=settings.CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS,
    call_timeout_seconds=settings.BACKEND_CALL_TIMEOUT_SECONDS,
)


async def _translate_mock(
    texts: list[str], source_lang: str, target_lang: str, option: int
) -> list[str]:
    return [f"[{target_lang}] {text}" for text in texts]


async def _translate_socket(
    texts: list[str], source_lang: str, target_lang: str, option: int
) -> list[str]:
    request_payload = {
        "source-text": texts,
        "source-lang": source_lang,
        "target-lang": target_lang,
        "option": option,
    }
    response_payload = await call_json_socket_backend(
        settings.TRANSLATION_BACKEND_HOST,
        settings.TRANSLATION_BACKEND_PORT,
        request_payload,
    )
    # Expected shape: this endpoint's own HTTP response structure, i.e.
    # {"source-text": [...], "target-text": [...], "source-lang": ...,
    #  "target-lang": ..., "option": ...}. We only need "target-text" here;
    # the rest is reconstructed from the original request in translate().
    return response_payload["target-text"]


_BACKENDS: dict[str, Callable[[list[str], str, str, int], "list[str]"]] = {
    "socket": _translate_socket,
    "mock": _translate_mock,
}


async def _run_backend(
    texts: list[str], source_lang: str, target_lang: str, option: int
) -> list[str]:
    backend_fn = _BACKENDS.get(settings.TRANSLATION_BACKEND)
    if backend_fn is None:
        raise ValueError(f"Unknown TRANSLATION_BACKEND '{settings.TRANSLATION_BACKEND}'")
    return await backend_fn(texts, source_lang, target_lang, option)


async def translate(request: TranslateRequest) -> TranslateResponse:
    logger.info(
        "translate request: %d string(s), %s -> %s, option=%s",
        len(request.source_text),
        request.source_lang,
        request.target_lang,
        request.option,
    )

    async def call():
        return await _run_backend(
            request.source_text, request.source_lang, request.target_lang, request.option
        )

    target_text = await _breaker.call(call)

    logger.info("translate completed: %d string(s)", len(target_text))
    return TranslateResponse(
        **{
            "source-text": request.source_text,
            "target-text": target_text,
            "source-lang": request.source_lang,
            "target-lang": request.target_lang,
            "option": request.option,
        }
    )
