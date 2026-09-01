# Semantic Matching & Translation API

Internal **FastAPI** service exposing three endpoints:

- `POST /api/semantic-match` — best-match lookup between a set of query
  strings and a corpus (pluggable backend).
- `POST /api/translate` — translate a list of strings between languages
  (pluggable backend; the real translation engine is being provided
  separately — see "Backend services" below).
- `POST /api/pass-through` — generic pass-through: whatever JSON you send
  is forwarded to a backend verbatim, and whatever the backend returns is
  sent back verbatim. No schema on either side.

## Ports

| Service | Address |
|---|---|
| This API | `localhost:8080` |
| `/api/semantic-match` backend | `localhost:9999` |
| `/api/translate` backend | `localhost:9998` |
| `/api/pass-through` backend | `localhost:9997` |

All are configurable — see [Configuration reference](#configuration-reference).

## Swagger UI

Once the server is running (see "Running locally" below):

- **Swagger UI: http://localhost:8080/docs**
- ReDoc: http://localhost:8080/redoc
- Raw OpenAPI schema: http://localhost:8080/openapi.json
- Visiting http://localhost:8080/ (the bare root) redirects to `/docs`
  automatically.

This comes for free with FastAPI — no extra setup. If it wasn't loading
before, the most likely cause was port `80`: binding to port `80` requires
root/`CAP_NET_BIND_SERVICE`, so a plain `uvicorn ... --port 80` run
locally fails silently into "connection refused" rather than serving
anything. The default dev port is now `8080` (unprivileged) specifically
to avoid that — see the Docker section for how production still exposes
the service more conventionally.

## Project layout

```
semantic-api/
├── app/
│   ├── main.py                    # FastAPI app, middleware & error handlers wired up
│   ├── config.py                  # All settings, via env vars / .env
│   ├── logging_config.py          # Optional logging setup
│   ├── rate_limit.py              # slowapi limiter instance
│   ├── core/
│   │   └── exceptions.py          # CircuitBreakerOpenError, BackendTimeoutError, BackendUnavailableError
│   ├── middleware/
│   │   ├── timeout.py             # Hard request-level timeout
│   │   └── access_log.py          # Optional access logging
│   ├── routers/
│   │   ├── semantic_match.py      # POST /api/semantic-match
│   │   ├── translate.py           # POST /api/translate
│   │   └── pass_through.py        # POST /api/pass-through
│   ├── schemas/
│   │   ├── semantic_match.py      # Request model; response is Any (pass-through)
│   │   └── translate.py           # Request/response models (hyphenated aliases)
│   └── services/
│       ├── circuit_breaker.py     # Async circuit breaker + timeout wrapper
│       ├── socket_client.py       # Generic newline-delimited JSON TCP client
│       ├── semantic_match_service.py  # Pluggable backend registry, no built-in algorithm
│       ├── translation_service.py     # Pluggable backend registry ("socket" + "mock")
│       └── pass_through_service.py    # Pluggable backend registry ("socket")
├── scripts/
│   ├── _socket_server_utils.py           # Shared TCP server helper (not part of the app)
│   ├── mock_semantic_match_backend.py    # Standalone reference backend, port 9999
│   ├── mock_translate_backend.py         # Standalone placeholder backend, port 9998
│   └── mock_pass_through_backend.py      # Standalone echo backend, port 9997
├── tests/
│   ├── conftest.py                # Starts all three mock backends for the test session
│   ├── test_semantic_match.py
│   ├── test_translate.py
│   ├── test_pass_through.py
│   └── test_socket_backend.py     # Explicit socket-integration + reliability tests
├── .github/workflows/ci.yml       # Lint + test + Docker build check
├── requirements.txt
├── pyproject.toml                 # ruff config
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## How each requirement was implemented

| Requirement | Implementation |
|---|---|
| No API keys | No auth middleware/dependency anywhere. Access control is left entirely to the network layer, as specified. |
| Timeouts on background calls | `app/services/circuit_breaker.py`'s `CircuitBreaker.call()` wraps every backend call in `asyncio.wait_for(..., timeout=BACKEND_CALL_TIMEOUT_SECONDS)`. There's also an outer, whole-request timeout (`app/middleware/timeout.py`, `REQUEST_TIMEOUT_SECONDS`). |
| Circuit breakers | `app/services/circuit_breaker.py` — CLOSED → OPEN → HALF_OPEN state machine, one instance per service (semantic matching, translation, pass-through). Open breaker → `503`; transport-level failures (connection refused, etc.) → `503`; timeouts → `504`. |
| Logging (optional) | `LOGGING_ENABLED` env var. When `false`, a `NullHandler` is installed and the logger level is set above `CRITICAL`, so log calls are cheap no-ops app-wide. |
| Rate limiting (internal DoS protection) | `slowapi`, keyed by client IP, with separate limits per endpoint (`RATE_LIMIT_SEMANTIC_MATCHING`, `RATE_LIMIT_TRANSLATE`, `RATE_LIMIT_PASS_THROUGH`) plus a global default. Returns `429`. |
| Swagger UI | Free with FastAPI — see "Swagger UI" above. |

## Backend services (socket)

All three endpoints delegate to their own **socket service backend**, on
separate ports:

```
/api/semantic-match  ->  localhost:9999
/api/translate         ->  localhost:9998
/api/pass-through       ->  localhost:9997
```

configured via `SEMANTIC_MATCHING_BACKEND_HOST`/`_PORT`,
`TRANSLATION_BACKEND_HOST`/`_PORT`, and
`PASS_THROUGH_BACKEND_HOST`/`_PORT` in `.env`.

> **The real translation backend is being provided separately.** This
> repo only includes a `mock` stand-in (offline placeholder, used by the
> test suite and available for local dev) — see `app/services/translation_service.py`
> and `scripts/mock_translate_backend.py`. Point `TRANSLATION_BACKEND_HOST`/`_PORT`
> at the real service once it's ready; no code changes needed as long as
> it speaks the wire protocol below.

### Wire protocol

Newline-delimited JSON over a plain TCP socket, one request per connection
(implemented in `app/services/socket_client.py`):

1. Open a TCP connection to `(host, port)`.
2. Write the JSON-encoded request payload, followed by a single `\n`.
3. Read a single line (terminated by `\n`) containing the JSON-encoded
   response payload.
4. Close the connection.

**The request/response payloads are exactly the same JSON structures as
each endpoint's own HTTP contract** — no envelope, no renaming:

- `/api/semantic-match` sends `{"targets": [...], "corpus": [...],
  "score": ...}` and expects back a JSON array of `{"query_index",
  "query", "match_index", "best_match", "similarity_score"}` objects —
  i.e. exactly this endpoint's HTTP response body.
- `/api/translate` sends `{"source-text": [...], "source-lang": ...,
  "target-lang": ..., "option": ...}` and expects back `{"source-text":
  [...], "target-text": [...], "source-lang": ..., "target-lang": ...,
  "option": ...}` — i.e. exactly this endpoint's HTTP response body.
- `/api/pass-through` sends the request body exactly as received and
  expects back exactly what the backend wants the HTTP response to be —
  no fixed shape at all, `{}` is valid on both sides.

### Reference / mock implementations (separate scripts)

Each endpoint has its own standalone mock backend script — they're
independent processes on independent ports, matching how the real
backends are deployed:

```bash
python -m scripts.mock_semantic_match_backend   # 0.0.0.0:9999
python -m scripts.mock_translate_backend         # 0.0.0.0:9998
python -m scripts.mock_pass_through_backend      # 0.0.0.0:9997
```

All three are self-contained (no import from `app/services/`), so it's
clear they're test/dev stand-ins and not part of the production service:

- `scripts/mock_semantic_match_backend.py` implements TF-IDF +
  cosine-similarity matching (`scikit-learn`) as its reference algorithm.
- `scripts/mock_translate_backend.py` implements the same
  `"[<target-lang>] <text>"` placeholder as the in-process `mock`
  translation backend.
- `scripts/mock_pass_through_backend.py` is a trivial echo server —
  whatever JSON it receives, it sends back.

`scripts/_socket_server_utils.py` is a small shared helper (newline-JSON
framing over `asyncio.start_server`) used by all three scripts — not part
of the public app.

The full test suite (`pytest tests/`) starts **all three** of these
servers automatically for the duration of the run (see
`tests/conftest.py`), so `SEMANTIC_MATCHING_BACKEND`/`TRANSLATION_BACKEND`/
`PASS_THROUGH_BACKEND` stay on their real default (`"socket"`) in tests
too — there's no separate stubbed-out code path to fall out of sync with
production.

### Pluggable backends, not a built-in algorithm

`app/services/semantic_match_service.py`,
`app/services/translation_service.py`, and
`app/services/pass_through_service.py` are all pure pluggable-backend
registries (a `dict[str, Callable]` keyed by the `*_BACKEND` setting) —
none ships a built-in scoring/translation algorithm as part of the
production code path:

- Semantic matching currently registers only `"socket"` (see above for
  why the TF-IDF logic isn't an in-process option here — it lives in the
  mock script instead).
- Translation registers `"socket"` and `"mock"`.
- Pass-through registers only `"socket"`.

Add a new backend by writing one function and adding it to the
`_BACKENDS` dict — the router, circuit breaker, and timeout wiring stay
untouched.

### No fixed response schema for semantic match / pass-through

`POST /api/semantic-match` and `POST /api/pass-through` both use
`response_model=Any` in their routers — FastAPI does not validate or
coerce the response at all. Whatever the selected backend returns is sent
back byte-for-byte, including `{}` or any other shape. This is deliberate:
it keeps the HTTP contract from being tightly coupled to one particular
backend's response shape. `app/schemas/semantic_match.py`'s
`SemanticMatchResult` class documents the *typical* shape a backend would
return, for OpenAPI/reference purposes only — it's not enforced.
`/api/pass-through` has no response schema at all, by design — it doesn't
even have a request schema; the body is read as a raw `dict[str, Any]`.

(`/api/translate`'s response is still a fixed `TranslateResponse` model,
since this API constructs that response itself from the backend's
`target-text` field rather than passing the backend's response through
directly — see `translate()` in `app/services/translation_service.py`.)

## Endpoints

### `POST /api/semantic-match`

Request:
```json
{
  "targets": ["How do I reset my password?"],
  "corpus": ["Steps to reset your account password", "How to cancel a subscription"],
  "score": 0.3
}
```

Typical response (backend-dependent — see "No fixed response schema" above):
```json
[
  {
    "query_index": 0,
    "query": "How do I reset my password?",
    "match_index": 0,
    "best_match": "Steps to reset your account password",
    "similarity_score": 0.42
  }
]
```

If the best similarity for a query is below `score`, `match_index` and
`best_match` are typically `null` — but again, this is just what the
reference backend does, not an enforced contract.

### `POST /api/translate`

Request:
```json
{
  "source-text": ["Hello, how are you?"],
  "source-lang": "en",
  "target-lang": "es",
  "option": 0
}
```

Response:
```json
{
  "source-text": ["Hello, how are you?"],
  "target-text": ["[es] Hello, how are you?"],
  "source-lang": "en",
  "target-lang": "es",
  "option": 0
}
```

The `[es]`-prefixed output above is from the `mock` backend
(`TRANSLATION_BACKEND=mock`) — swap in the real translation service once
it's deployed by pointing `TRANSLATION_BACKEND_HOST`/`_PORT` at it.

### `POST /api/pass-through`

Request: any JSON object, including `{}`.
```json
{"anything": "you want", "nested": {"a": 1}}
```

Response: exactly what the backend returns for that request — with the
reference `socket` backend (an echo server), that's the same object back:
```json
{"anything": "you want", "nested": {"a": 1}}
```

No request or response schema is checked — whatever is received is
forwarded and returned as-is.

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env

# In separate terminals, start all three mock backends (needed since the
# default TRANSLATION_BACKEND/SEMANTIC_MATCHING_BACKEND/PASS_THROUGH_BACKEND
# is "socket"):
python -m scripts.mock_semantic_match_backend
python -m scripts.mock_translate_backend
python -m scripts.mock_pass_through_backend

# Then the API itself:
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Then open http://localhost:8080/docs for Swagger UI.

## Running tests

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

No need to start the mock backends by hand for tests — `tests/conftest.py`
does that automatically for the whole session.

## Continuous Integration

`.github/workflows/ci.yml` runs on every push/PR to `main`:
1. `ruff check` (lint) — config in `pyproject.toml`.
2. `pytest` across Python 3.11 and 3.12.
3. A Docker build check (no push) to catch a broken `Dockerfile` early.

Run the same checks locally before pushing:
```bash
pip install ruff
ruff check app tests scripts
python -m pytest tests/ -v
```

## Docker

```bash
docker compose up --build
```

`docker-compose.yml` publishes port `8080:8080` on the host — this is
safe because the host itself is expected to be firewalled at the network
layer (UFW/security-group rules allowing inbound `:8080` only from
specific IPs, e.g. the web server), not because Docker's own network
isolation is doing the job. If UFW isn't set up yet on the host, do that
before deploying:
```bash
ufw allow from <web-server-ip> to any port 8080 proto tcp
ufw default deny incoming
```

It also brings up **three temporary mock backend services**, internal to
the compose network only (no host ports published):

- `semantic-match-mock` (port `9999`) running
  `scripts/mock_semantic_match_backend.py`.
- `translate-mock` (port `9998`) running `scripts/mock_translate_backend.py`
  — standing in for the real translation backend until it's deployed.
- `pass-through-mock` (port `9997`) running
  `scripts/mock_pass_through_backend.py`.

`semantic-api`'s `environment:` block overrides
`SEMANTIC_MATCHING_BACKEND_HOST`/`_PORT`,
`TRANSLATION_BACKEND_HOST`/`_PORT`, and
`PASS_THROUGH_BACKEND_HOST`/`_PORT` to point at these three services by
Docker Compose service name.

**Once a real backend is deployed, comment out (independently, as each
becomes available):**
- the `semantic-match-mock` service block + its two
  `SEMANTIC_MATCHING_BACKEND_HOST`/`_PORT` override lines, and/or
- the `translate-mock` service block + its two
  `TRANSLATION_BACKEND_HOST`/`_PORT` override lines, and/or
- the `pass-through-mock` service block + its two
  `PASS_THROUGH_BACKEND_HOST`/`_PORT` override lines

so `.env`'s real values apply again for whichever backend just went live.
Both `docker-compose.yml` and `Dockerfile` have `>>>` markers at the
relevant spots.

## Configuration reference

All settings are environment variables (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `HOST` / `PORT` | `0.0.0.0` / `8080` | Bind address for this API |
| `BACKEND_CALL_TIMEOUT_SECONDS` | `5.0` | Per-backend-call timeout |
| `REQUEST_TIMEOUT_SECONDS` | `10.0` | Whole-request hard ceiling |
| `CIRCUIT_BREAKER_FAIL_MAX` | `5` | Consecutive failures before opening |
| `CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS` | `30.0` | How long the breaker stays open before a trial call |
| `RATE_LIMIT_ENABLED` | `true` | Toggle rate limiting on/off |
| `RATE_LIMIT_DEFAULT` | `60/minute` | Fallback limit for any route |
| `RATE_LIMIT_SEMANTIC_MATCHING` | `30/minute` | Limit for `/api/semantic-match` |
| `RATE_LIMIT_TRANSLATE` | `30/minute` | Limit for `/api/translate` |
| `RATE_LIMIT_PASS_THROUGH` | `30/minute` | Limit for `/api/pass-through` |
| `LOGGING_ENABLED` | `true` | Turn logging on/off (per spec: optional) |
| `LOG_LEVEL` | `INFO` | Standard Python log levels |
| `LOG_JSON` | `false` | Structured JSON log lines instead of plain text |
| `SEMANTIC_MATCHING_BACKEND` | `socket` | Currently only `socket` is registered (see "Pluggable backends" above) |
| `SEMANTIC_MATCHING_BACKEND_HOST` / `_PORT` | `localhost` / `9999` | Where the semantic-match socket backend lives |
| `TRANSLATION_BACKEND` | `socket` | `socket` or `mock` |
| `TRANSLATION_BACKEND_HOST` / `_PORT` | `localhost` / `9998` | Where the translation socket backend lives |
| `PASS_THROUGH_BACKEND` | `socket` | Currently only `socket` is registered |
| `PASS_THROUGH_BACKEND_HOST` / `_PORT` | `localhost` / `9997` | Where the pass-through socket backend lives |

## Notes / things to confirm with you

1. **Translation backend** — only a `mock` stand-in is included, per your
   note that the real one is being provided separately. Point
   `TRANSLATION_BACKEND_HOST`/`_PORT` at it once it's ready; the wire
   protocol above is what it needs to speak.
2. **Port `8080` + Docker** — local dev now defaults to the unprivileged
   `8080` for both the API and the compose publish, so no root/
   `CAP_NET_BIND_SERVICE` is needed anywhere. Flag if you actually need
   the container to bind `80` internally (e.g. a reverse proxy in front
   expects it) and this can be adjusted.
3. **`/api/pass-through`'s real backend** — no shape was specified beyond
   `{}` in, `{}` out, so the reference implementation is a plain echo
   server. Let me know what the real backend should actually do with the
   payload if that's meant to be more than a passthrough placeholder.
