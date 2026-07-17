"""Lightweight performance timer — zero overhead when DICOM_PERF_LOG != '1'."""

import logging
import time
from contextlib import contextmanager

from utils.debug_flags import PERF_LOG
from utils.privacy.structural_events import log_structural_event

_logger = logging.getLogger("perf")


def perf_mark(label: str, **fields: object) -> None:
    """Log a point-in-time performance marker when PERF_LOG is enabled."""
    if not PERF_LOG:
        return
    log_structural_event(
        _logger,
        logging.INFO,
        "performance.mark",
        category=label,
        metrics=fields,
    )


@contextmanager
def perf_timer(label: str):
    """Context manager that logs elapsed time at DEBUG level when PERF_LOG is enabled."""
    if not PERF_LOG:
        yield
        return
    t0 = time.perf_counter()
    yield
    elapsed_ms = (time.perf_counter() - t0) * 1000
    log_structural_event(
        _logger,
        logging.INFO,
        "performance.timer",
        category=label,
        metrics={"elapsed_ms": elapsed_ms},
    )
