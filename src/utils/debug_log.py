"""
Debug Log Utility

Provides optional, safe file-based debug logging for agent/session debugging.
Logs are written only when enabled via environment variable; failures are
swallowed so the application never crashes due to logging.

Inputs:
    - debug_log(location, message, data, hypothesis_id) calls from application code
    - Environment: DICOMVIEWER_DEBUG_LOG (set to 1, true, or yes to enable)

Outputs:
    - When enabled: appends JSON lines to <project_root>/.cursor/debug.log
    - When disabled or on error: no side effects

Requirements:
    - Standard library only: pathlib, os, json, time
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict

# Project root: this file is src/utils/debug_log.py -> parent=utils, parent.parent=src, parent.parent.parent=project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Enable only when env is set to 1, true, or yes (case-insensitive). Default off.
_DEBUG_ENV = os.getenv("DICOMVIEWER_DEBUG_LOG", "0").strip().lower()
DEBUG_LOG_ENABLED = _DEBUG_ENV in ("1", "true", "yes")

# Annotation debug prints (console); set DICOMVIEWER_ANNOTATION_DEBUG=1 to enable.
_ANNOTATION_DEBUG_ENV = os.getenv("DICOMVIEWER_ANNOTATION_DEBUG", "0").strip().lower()
ANNOTATION_DEBUG_ENABLED = _ANNOTATION_DEBUG_ENV in ("1", "true", "yes")


def annotation_debug(msg: str) -> None:
    """Print annotation debug message to console only when DICOMVIEWER_ANNOTATION_DEBUG is set."""
    if ANNOTATION_DEBUG_ENABLED:
        print(f"[ANNOTATION DEBUG] {msg}")


def debug_log(
    location: str,
    message: str,
    data: Dict[str, Any],
    hypothesis_id: str = "",
) -> None:
    """
    Append one JSON log line to .cursor/debug.log when debug logging is enabled.

    Failures (missing dir, permission, disk full, etc.) are caught and ignored
    so the application remains stable.

    Args:
        location: Call site identifier (e.g. "undo_redo.py:90").
        message: Short description of the event.
        data: Arbitrary dict of context (must be JSON-serializable).
        hypothesis_id: Optional hypothesis/session tag (e.g. "A", "B", "D").
    """
    if not DEBUG_LOG_ENABLED:
        return
    try:
        log_dir = _PROJECT_ROOT / ".cursor"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "debug.log"
        payload = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception:
        pass
