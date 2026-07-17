"""
Debug Log Utility

Provides optional, safe file-based debug logging for agent/session debugging.
Logs are written only when enabled by the persisted user setting; failures are
swallowed so the application never crashes due to logging.

Inputs:
    - debug_log(location, message, data, hypothesis_id) calls from application code
    - Explicit runtime state loaded from the persisted Settings choice

Outputs:
    - When enabled: writes redacted JSON lines to protected per-user app storage
    - When disabled or on error: no side effects

Requirements:
    - Standard library only: pathlib, os, json, time
"""

import json
import os
import time
from pathlib import Path
from typing import Any

from utils.debug_flags import DEBUG_ANNOTATION
from utils.privacy.redaction import redact_diagnostic_value, redact_text
from utils.privacy.safe_storage import (
    DeletionResult,
    RetentionPolicy,
    atomic_write_private_text,
    get_private_app_dir,
    secure_unlink,
    write_retention_metadata,
)

_SOURCE_ROOT = Path(__file__).resolve().parent.parent.parent
_MAX_DEBUG_LOG_BYTES = 2 * 1024 * 1024
_MAX_DEBUG_LOG_AGE_SECONDS = 7 * 24 * 60 * 60
_debug_log_path_override: Path | None = None

# The persisted Settings value is the sole product-runtime authority.
_debug_log_enabled = False

# Annotation debug prints (console); set DICOMVIEWER_ANNOTATION_DEBUG=1 to enable.
_ANNOTATION_DEBUG_ENV = os.getenv("DICOMVIEWER_ANNOTATION_DEBUG", "0").strip().lower()
ANNOTATION_DEBUG_ENABLED = _ANNOTATION_DEBUG_ENV in ("1", "true", "yes")


def annotation_debug(msg: str) -> None:
    """Print annotation debug message to console only when DEBUG_ANNOTATION flag is enabled."""
    if DEBUG_ANNOTATION or ANNOTATION_DEBUG_ENABLED:  # Support both flag and env var
        print(f"[ANNOTATION DEBUG] {redact_text(msg)}")


def debug_log_path() -> Path:
    """Return the disclosed protected location used for opt-in diagnostics."""

    if _debug_log_path_override is not None:
        return _debug_log_path_override
    return get_private_app_dir("diagnostics") / "debug.jsonl"


def clear_debug_log(*, path: Path | None = None) -> DeletionResult:
    """Clear the optional diagnostic log and truthfully report the outcome."""

    try:
        removed = int(secure_unlink(path or debug_log_path()))
    except OSError:
        return DeletionResult(failed=1)
    return DeletionResult(removed=removed)


def prune_debug_log(*, path: Path | None = None, now: float | None = None) -> bool:
    """Remove diagnostic JSON lines older than 7 days, dropping malformed lines."""

    target = path or debug_log_path()
    if not target.exists():
        return False
    current = time.time() if now is None else now
    cutoff_ms = int((current - _MAX_DEBUG_LOG_AGE_SECONDS) * 1000)
    original = target.read_bytes()
    kept: list[bytes] = []
    for line in original.splitlines():
        try:
            payload = json.loads(line)
            timestamp = int(payload.get("timestamp", 0))
        except (AttributeError, TypeError, ValueError):
            continue
        if timestamp >= cutoff_ms:
            kept.append(line)
    if not kept:
        secure_unlink(target)
        return True
    retained = b"\n".join(kept) + b"\n"
    if retained == original:
        return False
    atomic_write_private_text(
        target,
        retained.decode("utf-8"),
        source_root=_SOURCE_ROOT,
    )
    return True


def configure_debug_logging(enabled: bool, *, path: Path | None = None) -> None:
    """Apply an explicit runtime choice and protected path, then enforce retention."""

    global _debug_log_enabled, _debug_log_path_override
    _debug_log_path_override = path
    _debug_log_enabled = enabled is True
    try:
        if _debug_log_enabled:
            prune_debug_log(path=path)
    except OSError:
        pass


def _bounded_log_bytes(existing: bytes, new_line: bytes) -> bytes:
    """Keep complete newest JSON lines within the exact byte cap."""

    combined = existing + new_line
    if len(combined) <= _MAX_DEBUG_LOG_BYTES:
        return combined
    tail = combined[-_MAX_DEBUG_LOG_BYTES:]
    first_newline = tail.find(b"\n")
    if first_newline >= 0:
        tail = tail[first_newline + 1 :]
    if len(new_line) > _MAX_DEBUG_LOG_BYTES:
        return b""
    return tail or new_line


def _read_bounded_existing(path: Path) -> bytes:
    """Read at most the retained byte cap from the tail of an existing log."""

    if not path.exists():
        return b""
    with path.open("rb") as stream:
        size = path.stat().st_size
        if size > _MAX_DEBUG_LOG_BYTES:
            stream.seek(-_MAX_DEBUG_LOG_BYTES, os.SEEK_END)
        return stream.read(_MAX_DEBUG_LOG_BYTES)


def debug_log(
    location: str,
    message: str,
    data: dict[str, Any],
    hypothesis_id: str = "",
) -> None:
    """
    Append one redacted JSON line in protected app storage when enabled.

    Failures (missing dir, permission, disk full, etc.) are caught and ignored
    so the application remains stable.

    Args:
        location: Call site identifier (e.g. "undo_redo.py:90").
        message: Short description of the event.
        data: Arbitrary dict of context (must be JSON-serializable).
        hypothesis_id: Optional hypothesis/session tag (e.g. "A", "B", "D").
    """
    if not _debug_log_enabled:
        return
    try:
        log_path = debug_log_path()
        prune_debug_log(path=log_path)
        payload = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": redact_diagnostic_value(hypothesis_id),
            "location": redact_diagnostic_value(location),
            "message": redact_diagnostic_value(message),
            "data": redact_diagnostic_value(data),
            "timestamp": int(time.time() * 1000),
        }
        existing = _read_bounded_existing(log_path)
        line = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
        combined = _bounded_log_bytes(existing, line)
        atomic_write_private_text(
            log_path,
            combined.decode("utf-8"),
            source_root=_SOURCE_ROOT,
        )
        write_retention_metadata(
            log_path.parent,
            RetentionPolicy(max_age_days=7, max_files=1),
            source_root=_SOURCE_ROOT,
        )
    except Exception:
        pass
