"""
Centralized application configuration.

All values are overridable via environment variables (or a .env file).
See .env.example for the full list of supported settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- General ---
    APP_NAME: str = "Semantic Matching & Translation API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "production"

    # --- Network ---
    # Local dev / test default: 0.0.0.0:8080 (unprivileged port, so
    # `uvicorn` doesn't need root to bind it). In Docker/production this is
    # published as needed -- see docker-compose.yml.
    HOST: str = "0.0.0.0"
    PORT: int = 8080

    # --- Auth ---
    # No API key auth by design (per spec: "API Keys: no"). Access control is
    # enforced at the network layer (private subnet + upstream web server).
    API_KEY_REQUIRED: bool = False

    # --- Timeouts ---
    # Applied to every call out to a "background service" (model inference,
    # translation backend, etc.) so a single slow dependency can never hang
    # a request indefinitely.
    BACKEND_CALL_TIMEOUT_SECONDS: float = 5.0
    # Hard ceiling for the whole HTTP request (belt-and-suspenders on top of
    # the per-call timeout above).
    REQUEST_TIMEOUT_SECONDS: float = 10.0

    # --- Circuit breaker ---
    CIRCUIT_BREAKER_FAIL_MAX: int = 5
    CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS: float = 30.0

    # --- Rate limiting (protects against internal DoS) ---
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "60/minute"
    RATE_LIMIT_SEMANTIC_MATCHING: str = "30/minute"
    RATE_LIMIT_TRANSLATE: str = "30/minute"
    RATE_LIMIT_PASS_THROUGH: str = "30/minute"

    # --- Logging (optional, per spec: "Logging: option") ---
    LOGGING_ENABLED: bool = True
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False

    # --- Semantic matching backend ---
    # "socket" -> calls an external socket service over TCP (see
    #             app/services/socket_client.py for the wire protocol).
    # "mock"   -> computes matches in-process with TF-IDF + cosine
    #             similarity (scikit-learn). Reference/test implementation
    #             only -- not intended as a production matching engine.
    SEMANTIC_MATCHING_BACKEND: str = "socket"
    SEMANTIC_MATCHING_BACKEND_HOST: str = "localhost"
    SEMANTIC_MATCHING_BACKEND_PORT: int = 9999

    # --- Translation backend ---
    # "socket" -> calls an external socket service over TCP, same protocol
    #             as above. This is the real backend; it's being provided
    #             separately and will be pointed at via
    #             TRANSLATION_BACKEND_HOST/_PORT once it's deployed.
    # "mock"   -> deterministic offline stand-in, used by the test suite
    #             (and available for local dev with no external
    #             dependency). No real translation engine included here.
    TRANSLATION_BACKEND: str = "socket"
    TRANSLATION_BACKEND_HOST: str = "localhost"
    TRANSLATION_BACKEND_PORT: int = 9998

    # --- Pass-through backend ---
    # Generic endpoint: whatever JSON the caller sends is forwarded as-is
    # to this backend, and whatever the backend returns is sent back as-is.
    # No request/response schema is enforced on either side. "socket" is
    # currently the only registered backend.
    PASS_THROUGH_BACKEND: str = "socket"
    PASS_THROUGH_BACKEND_HOST: str = "localhost"
    PASS_THROUGH_BACKEND_PORT: int = 9997

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
