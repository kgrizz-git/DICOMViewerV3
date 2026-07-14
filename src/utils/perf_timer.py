"""Lightweight performance timer — zero overhead when DICOM_PERF_LOG != '1'."""

import logging
import time
from contextlib import contextmanager

from utils.debug_flags import PERF_LOG

_logger = logging.getLogger("perf")


def perf_mark(label: str, **fields: object) -> None:
    """Log a point-in-time performance marker when PERF_LOG is enabled."""
    if not PERF_LOG:
        return
    if fields:
        field_text = " ".join(f"{key}={value}" for key, value in fields.items())
        _logger.info("[PERF] %s: %s", label, field_text)
    else:
        _logger.info("[PERF] %s", label)


@contextmanager
def perf_timer(label: str):
    """Context manager that logs elapsed time at DEBUG level when PERF_LOG is enabled."""
    if not PERF_LOG:
        yield
        return
    t0 = time.perf_counter()
    yield
    elapsed_ms = (time.perf_counter() - t0) * 1000
    _logger.info("[PERF] %s: %.1fms", label, elapsed_ms)
