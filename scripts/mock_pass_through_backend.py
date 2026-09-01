"""
Reference/mock implementation of the pass-through socket backend --
PASS_THROUGH_BACKEND_HOST/_PORT in app/config.py (localhost:9997 by
default).

Run standalone:
    python -m scripts.mock_pass_through_backend

Since /api/pass-through has no fixed schema on either side, this reference
backend is deliberately trivial: an echo server. Whatever JSON it
receives, it sends straight back. This is enough to prove the socket
plumbing and the "no schema enforced" behavior end-to-end; a real backend
would presumably do something with the payload instead of echoing it.

Wire protocol: newline-delimited JSON, one request per connection -- see
app/services/socket_client.py.
"""
import asyncio
import logging

from scripts._socket_server_utils import serve

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")

HOST = "0.0.0.0"
PORT = 9997


def handle(payload: dict) -> dict:
    return payload


async def _main():
    server = await serve("pass-through", handle, HOST, PORT)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(_main())
