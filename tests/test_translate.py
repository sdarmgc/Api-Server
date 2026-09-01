from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_translate_basic():
    payload = {
        "source-text": ["Hello", "Good morning"],
        "source-lang": "en",
        "target-lang": "es",
        "option": 0,
    }
    resp = client.post("/api/translate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["source-text"] == payload["source-text"]
    assert data["source-lang"] == "en"
    assert data["target-lang"] == "es"
    assert data["option"] == 0
    assert len(data["target-text"]) == 2
    assert data["target-text"][0].startswith("[es]")


def test_translate_empty_source_text_rejected():
    payload = {
        "source-text": [],
        "source-lang": "en",
        "target-lang": "es",
        "option": 0,
    }
    resp = client.post("/api/translate", json=payload)
    assert resp.status_code == 422


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
