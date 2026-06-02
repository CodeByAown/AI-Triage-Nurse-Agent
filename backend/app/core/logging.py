import io
import logging
import sys

import structlog

from app.core.config import settings


def _safe_stdout():
    """Return a UTF-8 safe stdout wrapper (fixes Windows CP1252 encoding errors)."""
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        return io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
        )
    return sys.stdout


def setup_logging() -> None:
    log_level = logging.DEBUG if settings.app_env == "development" else logging.INFO
    safe_out = _safe_stdout()

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.app_env == "development":
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=False),  # no ANSI on Windows cmd
        ]
    else:
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(safe_out),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=safe_out,
        level=log_level,
    )


logger = structlog.get_logger()
