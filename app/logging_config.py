"""
Logging setup. Logging is optional (per spec) and controlled by the
LOGGING_ENABLED environment variable. When disabled, a NullHandler is
installed so log calls throughout the app remain cheap no-ops rather than
requiring conditional checks everywhere.
"""
import logging
import sys

from app.config import settings


def configure_logging() -> None:
    root_logger = logging.getLogger("app")
    root_logger.handlers.clear()

    if not settings.LOGGING_ENABLED:
        root_logger.addHandler(logging.NullHandler())
        root_logger.setLevel(logging.CRITICAL + 1)
        return

    handler = logging.StreamHandler(sys.stdout)

    if settings.LOG_JSON:
        fmt = (
            '{"timestamp":"%(asctime)s","level":"%(levelname)s",'
            '"logger":"%(name)s","message":"%(message)s"}'
        )
    else:
        fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    handler.setFormatter(logging.Formatter(fmt))
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.LOG_LEVEL.upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"app.{name}")
