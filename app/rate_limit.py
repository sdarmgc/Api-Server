"""
Rate limiting setup (slowapi / limits), keyed by client IP.

This exists to protect against internal DoS (spec requirement) -- e.g. a
misbehaving internal caller or a bug in the upstream web server that causes
a burst/retry storm. Since there's no API key, the limiter keys on remote
address; if this service ends up behind a proxy that doesn't preserve the
real client IP, set `X-Forwarded-For` correctly upstream or adjust
`key_func` accordingly.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT] if settings.RATE_LIMIT_ENABLED else [],
    enabled=settings.RATE_LIMIT_ENABLED,
)
