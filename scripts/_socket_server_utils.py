"""
Small shared helper for the mock backend scripts (mock_semantic_matching_
backend.py, mock_translate_backend.py). Not part of the public app -- just
avoids duplicating the asyncio/newline-delimited-JSON boilerplate between
the two scripts, which are otherwise fully independent and can be run,
deployed, or discarded separately.

Implements the server side of the protocol documented in
app/services/socket_client.py: one TCP connection per request, a single
newline-delimited JSON line in, a single newline-delimited JSON line out.
"""
import asyncio
import json
import logging
from collections.abc import Callable

logger = logging.getLogger("mock_backend")


def _make_client_handler(name: str, handle_payload: Callable[[dict], dict | list]):
    async def _handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer = writer.get_extra_info("peername")
        try:
            line = await reader.readline()
            if not line:
                return
            payload = json.loads(line.decode("utf-8"))
            logger.info("[%s] request from %s: keys=%s", name, peer, list(payload.keys()))

            response = handle_payload(payload)

            writer.write(json.dumps(response).encode("utf-8") + b"\n")
            await writer.drain()
        except Exception:
            logger.exception("[%s] error handling request from %s", name, peer)
            try:
                writer.write(json.dumps({"error": "internal_error"}).encode("utf-8") + b"\n")
                await writer.drain()
            except (ConnectionError, OSError):
                pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass

    return _handle_client


async def serve(
    name: str, handle_payload: Callable[[dict], dict | list], host: str, port: int
) -> asyncio.AbstractServer:
    server = await asyncio.start_server(_make_client_handler(name, handle_payload), host, port)
    logger.info("[%s] mock socket backend listening on %s:%s", name, host, port)
    return server
