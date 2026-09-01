class CircuitBreakerOpenError(Exception):
    """Raised when a call is rejected because the circuit breaker is open."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        super().__init__(f"Circuit breaker open for service '{service_name}'")


class BackendTimeoutError(Exception):
    """Raised when a background service call exceeds its allotted timeout."""

    def __init__(self, service_name: str, timeout_seconds: float):
        self.service_name = service_name
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Call to service '{service_name}' timed out after {timeout_seconds}s"
        )


class BackendUnavailableError(Exception):
    """Raised when a background service call fails at the transport level
    (connection refused, DNS failure, connection reset, etc.) rather than
    timing out."""

    def __init__(self, service_name: str, reason: str):
        self.service_name = service_name
        self.reason = reason
        super().__init__(f"Call to service '{service_name}' failed: {reason}")
