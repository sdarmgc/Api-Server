"""
Session-wide test fixtures.

Default settings point /api/semantic-match, /api/translate, and
/api/pass-through at three separate socket backends (localhost:9999,
localhost:9998, and localhost:9997 respectively -- see app/config.py). To
keep the test suite fully self-contained (no external services required
to run `pytest`), this fixture starts all three reference mock servers
(scripts/mock_semantic_match_backend.py, scripts/mock_translate_backend.py,
scripts/mock_pass_through_backend.py) in-process before any test runs, and
tears them down afterward.
"""
import asyncio
import threading

import pytest

from app.config import settings
from scripts import (
    mock_pass_through_backend,
    mock_semantic_match_backend,
    mock_translate_backend,
)
from scripts._socket_server_utils import serve


def _start_mock_server(name: str, handle, port: int):
    """Runs a mock socket server on its own event loop in a background
    thread, and returns (thread, holder) where holder carries the loop and
    server object needed to shut it down later."""
    ready = threading.Event()
    holder: dict = {}

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        holder["loop"] = loop

        server = loop.run_until_complete(serve(name, handle, "localhost", port))
        holder["server"] = server
        ready.set()
        loop.run_forever()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    ready.wait(timeout=5)
    return thread, holder


def _stop_mock_server(thread: threading.Thread, holder: dict):
    loop = holder["loop"]
    server = holder["server"]
    loop.call_soon_threadsafe(server.close)
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=5)


@pytest.fixture(scope="session", autouse=True)
def mock_socket_backends():
    servers = [
        _start_mock_server(
            "semantic-match",
            mock_semantic_match_backend.handle,
            settings.SEMANTIC_MATCHING_BACKEND_PORT,
        ),
        _start_mock_server(
            "translate",
            mock_translate_backend.handle,
            settings.TRANSLATION_BACKEND_PORT,
        ),
        _start_mock_server(
            "pass-through",
            mock_pass_through_backend.handle,
            settings.PASS_THROUGH_BACKEND_PORT,
        ),
    ]

    yield

    for thread, holder in servers:
        _stop_mock_server(thread, holder)
