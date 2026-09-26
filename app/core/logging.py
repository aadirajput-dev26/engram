"""
Structured logging configuration.
Prevents secret and raw document content leakage in log output.
"""
from __future__ import annotations

import logging
import re
import sys
from typing import Optional


# Patterns that should never appear in log output
_SECRET_PATTERNS = re.compile(
    r"(api_key|secret|password|token|credential)"
    r"\s*[=:]\s*['\"]?([^\s'\"]{4,})['\"]?",
    re.IGNORECASE,
)

_REDACTION = "***REDACTED***"


class SecretRedactingFilter(logging.Filter):
    """Filter that redacts secrets from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _SECRET_PATTERNS.sub(
                lambda m: f"{m.group(1)}={_REDACTION}", record.msg
            )
        if record.args:
            new_args = []
            for arg in (record.args if isinstance(record.args, tuple) else (record.args,)):
                if isinstance(arg, str):
                    arg = _SECRET_PATTERNS.sub(
                        lambda m: f"{m.group(1)}={_REDACTION}", arg
                    )
                new_args.append(arg)
            record.args = tuple(new_args) if len(new_args) > 1 else new_args[0]
        return True


def setup_logging(level: Optional[str] = None) -> None:
    """Configure structured logging for the application."""
    log_level = getattr(logging, (level or "INFO").upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(SecretRedactingFilter())

    root = logging.getLogger()
    root.setLevel(log_level)
    # Remove existing handlers to avoid duplicates
    root.handlers.clear()
    root.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger."""
    return logging.getLogger(name)
