from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_pass_through_empty_object():
    resp = client.post("/api/pass-through", json={})
    assert resp.status_code == 200
    assert resp.json() == {}


def test_pass_through_echoes_arbitrary_payload():
    payload = {"anything": ["goes", "here"], "nested": {"a": 1, "b": None}}
    resp = client.post("/api/pass-through", json=payload)
    assert resp.status_code == 200
    assert resp.json() == payload


def test_pass_through_no_body_defaults_to_empty_object():
    resp = client.post("/api/pass-through")
    assert resp.status_code == 200
    assert resp.json() == {}
