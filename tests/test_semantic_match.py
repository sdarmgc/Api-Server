from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_semantic_match_basic():
    payload = {
        "targets": ["How do I reset my password?"],
        "corpus": [
            "Steps to reset your account password",
            "How to cancel a subscription",
        ],
        "score": 0,
    }
    resp = client.post("/api/semantic-match", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["query_index"] == 0
    assert data[0]["query"] == payload["targets"][0]
    assert data[0]["match_index"] == 0
    assert data[0]["best_match"] == payload["corpus"][0]
    assert data[0]["similarity_score"] > 0


def test_semantic_match_below_threshold_returns_null_match():
    payload = {
        "targets": ["completely unrelated gibberish zzz"],
        "corpus": ["totally different topic qqq"],
        "score": 0.99,
    }
    resp = client.post("/api/semantic-match", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["match_index"] is None
    assert data[0]["best_match"] is None


def test_semantic_match_single_char_words_does_not_crash():
    # Regression test: single-character tokens used to produce an empty
    # TF-IDF vocabulary and raise a 500.
    payload = {"targets": ["a"], "corpus": ["b"], "score": 0}
    resp = client.post("/api/semantic-match", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["query_index"] == 0


def test_semantic_match_empty_targets_rejected():
    payload = {"targets": [], "corpus": ["a"], "score": 0}
    resp = client.post("/api/semantic-match", json=payload)
    assert resp.status_code == 422


def test_semantic_match_response_passes_through_arbitrary_backend_shape(monkeypatch):
    # Regression test: the response is not validated/coerced against any
    # fixed schema -- whatever the backend returns comes back verbatim,
    # including something as minimal as {}.
    from app.services import semantic_match_service

    async def fake_match(request):
        return {}

    monkeypatch.setattr(semantic_match_service, "match", fake_match)

    payload = {"targets": ["a"], "corpus": ["b"], "score": 0}
    resp = client.post("/api/semantic-match", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {}


def test_semantic_match_response_passes_through_nonstandard_list(monkeypatch):
    # Same idea, but a shape that wouldn't have validated against the old
    # list[SemanticMatchResult] response_model (extra/different fields).
    from app.services import semantic_match_service

    async def fake_match(request):
        return [{"unexpected_field": "whatever the backend wants to send"}]

    monkeypatch.setattr(semantic_match_service, "match", fake_match)

    payload = {"targets": ["a"], "corpus": ["b"], "score": 0}
    resp = client.post("/api/semantic-match", json=payload)
    assert resp.status_code == 200
    assert resp.json() == [{"unexpected_field": "whatever the backend wants to send"}]
