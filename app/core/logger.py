"""
app/core/logger.py
==================
Structured, levelled logging factory for EcoRecon AI.

Design decisions:
  - Named loggers per module keep log lines attributable.
  - Log level is driven entirely by Settings — no hard-coded values.
  - Format is JSON-friendly in production; human-readable in development.
  - A single `get_logger` factory is the ONLY way to obtain a logger,
    preventing ad-hoc `logging.getLogger()` calls scattered in the codebase.
"""

import logging
import sys
from typing import Optional

from app.core.config import get_settings


_HUMAN_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
)
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

# Module-level registry to prevent duplicate handler attachment
_configured_loggers: set[str] = set()


def _build_handler(is_production: bool) -> logging.StreamHandler:
    """Construct and return a configured stream handler."""
    handler = logging.StreamHandler(sys.stdout)

    if is_production:
        # Structured one-liner for log aggregation pipelines (CloudWatch, GCP, etc.)
        fmt = logging.Formatter(
            '{"time":"%(asctime)s","level":"%(levelname)s",'
            '"logger":"%(name)s","line":%(lineno)d,"msg":"%(message)s"}',
            datefmt=_DATE_FORMAT,
        )
    else:
        fmt = logging.Formatter(_HUMAN_FORMAT, datefmt=_DATE_FORMAT)

    handler.setFormatter(fmt)
    return handler


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Return a named, fully configured logger.

    Args:
        name: Typically ``__name__`` of the calling module.
              Defaults to the root ``ecorecon`` logger.

    Returns:
        A ``logging.Logger`` instance ready for use.

    Example::
        from app.core.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Declaration stored", extra={"record_id": record_id})
    """
    settings = get_settings()
    logger_name = name or "ecorecon"

    logger = logging.getLogger(logger_name)

    if logger_name not in _configured_loggers:
        logger.setLevel(settings.log_level)
        logger.addHandler(_build_handler(is_production=settings.is_production))
        logger.propagate = False
        _configured_loggers.add(logger_name)

    return logger


# Convenience root logger — use `get_logger(__name__)` in modules
root_logger = get_logger("ecorecon")
