"""
Generic newline-delimited JSON TCP socket client, used to call the
"socket service" backends for semantic matching and translation.

Wire protocol (simple, one-shot per request):
  1. Open a TCP connection to (host, port).
  2. Write the JSON-encoded request payload, followed by a single "\n".
  3. Read a single line (terminated by "\n") containing the JSON-encoded
     response payload.
  4. Close the connection.

The request/response payloads are exactly the same JSON structures used by
this API's own HTTP endpoints (see app/schemas/), so a real backend service
can be wired in without any field renaming or translation layer.

A fresh connection is opened per call rather than pooling one, so the
existing CircuitBreaker/timeout wrapping (app/services/circuit_breaker.py)
fully governs each call's lifecycle -- no persistent-connection edge cases
(half-open sockets, stale connections after a backend restart, etc.) to
reason about.
"""
import asyncio
import json
from typing import Any

from app.logging_config import get_logger

logger = get_logger("socket_client")

# Generous upper bound on a single response line; guards against a
# misbehaving backend streaming unbounded data into memory.
_MAX_LINE_BYTES = 10 * 1024 * 1024  # 10 MB


async def call_json_socket_backend(
    host: str, port: int, payload: dict[str, Any]
) -> dict[str, Any]:
    logger.debug("Connecting to socket backend %s:%s", host, port)
    reader, writer = await asyncio.open_connection(host, port)
    try:
        request_line = json.dumps(payload).encode("utf-8") + b"\n"
        writer.write(request_line)
        await writer.drain()

        response_line = await reader.readline()
        if not response_line:
            raise ConnectionError(
                f"Socket backend {host}:{port} closed the connection with no response"
            )
        if len(response_line) > _MAX_LINE_BYTES:
            raise ValueError(
                f"Socket backend {host}:{port} response exceeded {_MAX_LINE_BYTES} bytes"
            )

        return json.loads(response_line.decode("utf-8"))
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionError, OSError):
            pass
