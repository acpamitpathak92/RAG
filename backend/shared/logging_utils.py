"""Central logging setup.

Two levels are used throughout the pipeline:
- INFO: always-on, high-level lifecycle events (a query came in, a stage finished,
  a response went out) - cheap enough to leave on by default so you can see a
  request's path through the system without extra config.
- DEBUG: detailed per-stage internals (chunk counts, scores, timings) - only
  emitted when verbose logging is turned on.

Toggle verbose logging with the VERBOSE_LOGGING env var (or `verbose_logging: true`
in .env) - see backend/shared/config/settings.py. Off by default.
"""

import logging
import sys
import time
from contextlib import contextmanager

from backend.shared.config.settings import get_settings

_CONFIGURED = False


def configure_logging() -> None:
    """Idempotent - safe to call from every module that wants a logger."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = logging.DEBUG if get_settings().verbose_logging else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    logging.getLogger("backend").setLevel(level)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)


@contextmanager
def log_stage(logger: logging.Logger, stage_name: str, **fields):
    """Wraps one pipeline stage: logs entry at DEBUG (with any context fields) and
    exit at INFO with elapsed time, so a request's path through the system - and
    where time was spent - is visible in the logs end to end.
    """
    context = " ".join(f"{key}={value}" for key, value in fields.items())
    logger.debug(f"-> {stage_name} start {context}".rstrip())
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(f"{stage_name} done in {elapsed_ms:.1f}ms")
