from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.core.exceptions import (
    BackendTimeoutError,
    BackendUnavailableError,
    CircuitBreakerOpenError,
)
from app.logging_config import configure_logging, get_logger
from app.middleware.access_log import AccessLogMiddleware
from app.middleware.timeout import RequestTimeoutMiddleware
from app.rate_limit import limiter
from app.routers import semantic_match, translate

configure_logging()
logger = get_logger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting %s v%s (env=%s) on %s:%s",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.ENVIRONMENT,
        settings.HOST,
        settings.PORT,
    )
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Internal API providing semantic text matching and translation. "
        "No API key is required — access is restricted at the network "
        "layer (private subnet, reachable only via the upstream web "
        "server). Swagger UI: /docs · ReDoc: /redoc · OpenAPI JSON: "
        "/openapi.json"
    ),
    lifespan=lifespan,
)

# --- Rate limiting ---
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    logger.warning("Rate limit exceeded for %s on %s", request.client.host, request.url.path)
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )


# --- Circuit breaker / timeout error handlers ---
@app.exception_handler(CircuitBreakerOpenError)
async def circuit_breaker_open_handler(request: Request, exc: CircuitBreakerOpenError):
    logger.error("Circuit breaker open: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": f"Service '{exc.service_name}' is temporarily unavailable."},
    )


@app.exception_handler(BackendTimeoutError)
async def backend_timeout_handler(request: Request, exc: BackendTimeoutError):
    logger.error("Backend timeout: %s", exc)
    return JSONResponse(
        status_code=504,
        content={
            "detail": (
                f"Service '{exc.service_name}' did not respond within "
                f"{exc.timeout_seconds}s."
            )
        },
    )


@app.exception_handler(BackendUnavailableError)
async def backend_unavailable_handler(request: Request, exc: BackendUnavailableError):
    logger.error("Backend unavailable: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": f"Service '{exc.service_name}' is unavailable: {exc.reason}"},
    )


# --- Middleware (order matters: outermost added last executes first) ---
app.add_middleware(RequestTimeoutMiddleware)
app.add_middleware(AccessLogMiddleware)
app.add_middleware(SlowAPIMiddleware)

# --- Routers ---
app.include_router(semantic_match.router)
app.include_router(translate.router)


@app.get("/health", tags=["Health"], summary="Liveness/readiness probe")
async def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def root():
    # Convenience redirect so visiting the base URL lands on Swagger UI
    # instead of a 404 -- there's no dedicated "/" endpoint otherwise.
    return RedirectResponse(url="/docs")
