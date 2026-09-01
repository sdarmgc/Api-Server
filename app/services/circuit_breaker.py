"""
A small, dependency-free async circuit breaker.

States:
    CLOSED     -> calls pass through normally.
    OPEN       -> calls are rejected immediately (fail fast) until the reset
                  timeout elapses.
    HALF_OPEN  -> one trial call is allowed through; success closes the
                  breaker again, failure re-opens it.

Every call is also wrapped in asyncio.wait_for so a hung dependency can
never block the caller past BACKEND_CALL_TIMEOUT_SECONDS (spec requirement:
"Always set timeouts for background service calls"). A timeout counts as a
failure for the purposes of tripping the breaker.
"""
import asyncio
import time
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import TypeVar

from app.core.exceptions import (
    BackendTimeoutError,
    BackendUnavailableError,
    CircuitBreakerOpenError,
)
from app.logging_config import get_logger

logger = get_logger("circuit_breaker")

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        fail_max: int,
        reset_timeout_seconds: float,
        call_timeout_seconds: float,
    ):
        self.name = name
        self.fail_max = fail_max
        self.reset_timeout_seconds = reset_timeout_seconds
        self.call_timeout_seconds = call_timeout_seconds

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    async def _record_success(self) -> None:
        async with self._lock:
            self._failure_count = 0
            if self._state != CircuitState.CLOSED:
                logger.info("Circuit '%s' closing after successful trial call", self.name)
            self._state = CircuitState.CLOSED
            self._opened_at = None

    async def _record_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            if self._failure_count >= self.fail_max:
                if self._state != CircuitState.OPEN:
                    logger.warning(
                        "Circuit '%s' OPENING after %d consecutive failures",
                        self.name,
                        self._failure_count,
                    )
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()

    async def _pre_call_check(self) -> None:
        async with self._lock:
            if self._state == CircuitState.OPEN:
                assert self._opened_at is not None
                elapsed = time.monotonic() - self._opened_at
                if elapsed >= self.reset_timeout_seconds:
                    logger.info(
                        "Circuit '%s' entering HALF_OPEN trial after %.1fs",
                        self.name,
                        elapsed,
                    )
                    self._state = CircuitState.HALF_OPEN
                else:
                    raise CircuitBreakerOpenError(self.name)

    async def call(self, func: Callable[[], Awaitable[T]]) -> T:
        await self._pre_call_check()
        try:
            result = await asyncio.wait_for(func(), timeout=self.call_timeout_seconds)
        except asyncio.TimeoutError:
            await self._record_failure()
            raise BackendTimeoutError(self.name, self.call_timeout_seconds)
        except (ConnectionError, OSError) as exc:
            # Transport-level failure (connection refused, reset, DNS
            # failure, etc.) -- distinct from a timeout, but still counts
            # as a failure for the breaker and still deserves a clean HTTP
            # error rather than a raw exception leaking to the client.
            await self._record_failure()
            raise BackendUnavailableError(self.name, str(exc))
        except Exception:
            await self._record_failure()
            raise
        else:
            await self._record_success()
            return result
