"""
Reference/mock implementation of the semantic-match socket backend --
SEMANTIC_MATCHING_BACKEND_HOST/_PORT in app/config.py (localhost:9999 by
default).

Run standalone:
    python -m scripts.mock_semantic_match_backend

This is a separate, independently runnable script from
mock_translate_backend.py -- semantic-match and translate are two
different backend services on two different ports, so their mocks are
kept separate too, matching how a real deployment would look (and how
docker-compose.yml wires them up).

app/services/semantic_match_service.py itself ships with no built-in
matching algorithm -- it's purely the pluggable-backend wiring (registry +
circuit breaker/timeout). The TF-IDF + cosine-similarity reference
implementation lives here instead, self-contained, so it's clear this is a
stand-in for a real backend rather than part of the production service.
The test suite starts this exact script (see tests/conftest.py) so tests
exercise a real socket talking to this real (if simplistic) algorithm, not
a stub.

Wire protocol: newline-delimited JSON, one request per connection -- see
app/services/socket_client.py. Request/response use exactly the same JSON
structure as POST /api/semantic-match's own HTTP contract:
    in  -> {"targets": [...], "corpus": [...], "score": ...}
    out -> [{"query_index", "query", "match_index", "best_match",
             "similarity_score"}, ...]
"""
import asyncio
import logging

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from scripts._socket_server_utils import serve

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")

HOST = "0.0.0.0"
PORT = 9999


def _compute_matches(targets: list[str], corpus: list[str], min_score: float) -> list[dict]:
    # token_pattern includes single-character tokens (default sklearn
    # pattern requires 2+ chars and silently drops short words like "a" or
    # "I", which can otherwise yield an empty vocabulary and raise).
    vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b")

    try:
        # Fit on the union of targets + corpus so both are projected into
        # the same vector space.
        vectorizer.fit(targets + corpus)
        target_matrix = vectorizer.transform(targets)
        corpus_matrix = vectorizer.transform(corpus)
        similarity_matrix = cosine_similarity(target_matrix, corpus_matrix)
    except ValueError:
        # e.g. every input was pure stop-words/punctuation and produced an
        # empty vocabulary. Treat as "no similarity" rather than erroring.
        similarity_matrix = np.zeros((len(targets), len(corpus)))

    results: list[dict] = []
    for i, query in enumerate(targets):
        row = similarity_matrix[i]
        best_idx = int(row.argmax()) if len(row) > 0 else None
        best_score = float(row[best_idx]) if best_idx is not None else 0.0

        if best_idx is not None and best_score >= min_score:
            results.append(
                {
                    "query_index": i,
                    "query": query,
                    "match_index": best_idx,
                    "best_match": corpus[best_idx],
                    "similarity_score": round(best_score, 6),
                }
            )
        else:
            results.append(
                {
                    "query_index": i,
                    "query": query,
                    "match_index": None,
                    "best_match": None,
                    "similarity_score": round(best_score, 6),
                }
            )
    return results


def handle(payload: dict) -> list:
    targets = payload["targets"]
    corpus = payload["corpus"]
    min_score = payload.get("score", 0)
    return _compute_matches(targets, corpus, min_score)


async def _main():
    server = await serve("semantic-match", handle, HOST, PORT)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(_main())
