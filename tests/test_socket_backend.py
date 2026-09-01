"""
Tests specifically exercising the socket-backend integration path (the
default TRANSLATION_BACKEND / SEMANTIC_MATCHING_BACKEND = "socket"). The
mock_socket_backends fixture in conftest.py runs two real, separate TCP
servers for the whole test session -- one for semantic-match
(localhost:9999), one for translate (localhost:9998) -- so these hit
actual sockets, not a mock/stub of the client.
"""
import asyncio

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.socket_client import call_json_socket_backend

client = TestClient(app)


def test_semantic_match_uses_real_socket_backend():
    payload = {
        "targets": ["reset my password"],
        "corpus": ["password reset instructions", "billing question"],
        "score": 0,
    }
    resp = client.post("/api/semantic-match", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["match_index"] == 0


def test_translate_uses_real_socket_backend():
    payload = {
        "source-text": ["Good evening"],
        "source-lang": "en",
        "target-lang": "fr",
        "option": 0,
    }
    resp = client.post("/api/translate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["target-text"] == ["[fr] Good evening"]


@pytest.mark.anyio
async def test_socket_client_raw_protocol():
    # Talk to the mock backend directly to pin down the wire protocol
    # itself, independent of the FastAPI layer.
    response = await call_json_socket_backend(
        "localhost",
        settings.SEMANTIC_MATCHING_BACKEND_PORT,
        {"targets": ["a"], "corpus": ["a"], "score": 0},
    )
    assert isinstance(response, list)
    assert response[0]["query_index"] == 0


def test_semantic_match_and_translate_use_different_ports():
    # Regression test: semantic-match and translate are two separate
    # backend services on two separate ports (9999 / 9998), not one
    # shared service on 9999 as in an earlier iteration.
    assert settings.SEMANTIC_MATCHING_BACKEND_PORT == 9999
    assert settings.TRANSLATION_BACKEND_PORT == 9998
    assert settings.SEMANTIC_MATCHING_BACKEND_PORT != settings.TRANSLATION_BACKEND_PORT


@pytest.mark.anyio
async def test_translate_socket_client_raw_protocol():
    # Same check as test_socket_client_raw_protocol above, but against the
    # translate mock server specifically, on its own port.
    response = await call_json_socket_backend(
        "localhost",
        settings.TRANSLATION_BACKEND_PORT,
        {
            "source-text": ["hi"],
            "source-lang": "en",
            "target-lang": "de",
            "option": 0,
        },
    )
    assert response["target-text"] == ["[de] hi"]


@pytest.mark.anyio
async def test_socket_client_times_out_on_unreachable_backend():
    # Port 9 is the discard port; nothing will respond, so this should hit
    # the timeout path rather than hang the test suite.
    with pytest.raises((asyncio.TimeoutError, OSError, ConnectionError)):
        await asyncio.wait_for(
            call_json_socket_backend("localhost", 9, {"targets": ["x"], "corpus": ["y"]}),
            timeout=1.0,
        )


def test_semantic_match_returns_503_when_backend_unreachable(monkeypatch):
    # Point at a port nothing is listening on and confirm the circuit
    # breaker's timeout/failure handling surfaces as a clean 503/504
    # rather than a raw connection error leaking to the client.
    monkeypatch.setattr(settings, "SEMANTIC_MATCHING_BACKEND_PORT", 65530)
    monkeypatch.setattr(settings, "BACKEND_CALL_TIMEOUT_SECONDS", 1.0)

    # Reset the module-level circuit breaker's failure count between test
    # runs isn't necessary here since a fresh TestClient/process state is
    # used, but a single call is enough to prove the failure path.
    resp = client.post(
        "/api/semantic-match",
        json={"targets": ["a"], "corpus": ["b"], "score": 0},
    )
    assert resp.status_code in (503, 504)
