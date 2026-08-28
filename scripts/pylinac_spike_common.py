"""
Shared helpers for pylinac ACR spike scripts (Phase 0 ``results_data`` fixture dumps).

Used by ``spike_pylinac_acrct.py`` and ``spike_pylinac_acrmri.py`` to call
``analyzer.results_data(as_dict=True)``, redact filesystem paths, and write JSON
for ``tests/fixtures/qa/``. Maintainer-only: requires local gitignored phantom data.
"""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

# Absolute Unix paths and Windows drive paths (conservative redaction for fixtures).
_UNIX_ABS = re.compile(r"(?<![\w./-])(/[\w./-]+)")
_WIN_ABS = re.compile(r"(?<![\w:])[A-Za-z]:[\\/][\w. \\-/]+")


def _looks_like_absolute_path(text: str) -> bool:
    if not text or len(text) < 3:
        return False
    if text.startswith("/"):
        return True
    if len(text) >= 3 and text[1] == ":" and text[2] in ("/", "\\"):
        return True
    try:
        PureWindowsPath(text).is_absolute()
    except ValueError:
        return False
    else:
        if PureWindowsPath(text).is_absolute():
            return True
    try:
        return PurePosixPath(text).is_absolute()
    except ValueError:
        return False


def redact_paths_in_value(value: Any) -> Any:
    """Recursively redact absolute path strings in dict/list trees."""
    if isinstance(value, str):
        if _looks_like_absolute_path(value):
            return "<redacted-path>"
        replaced = _WIN_ABS.sub("<redacted-path>", value)
        replaced = _UNIX_ABS.sub("<redacted-path>", replaced)
        return replaced
    if isinstance(value, dict):
        return {str(k): redact_paths_in_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_paths_in_value(v) for v in value]
    return value


def results_data_as_dict(analyzer: Any) -> dict[str, Any]:
    """Return ``results_data(as_dict=True)`` as a plain dict."""
    data = analyzer.results_data(as_dict=True)
    if not isinstance(data, dict):
        raise TypeError(f"Expected dict from results_data(as_dict=True), got {type(data)!r}")
    return data


def write_redacted_results_dump(
    analyzer: Any,
    out_path: Path,
    *,
    indent: int = 2,
) -> Path:
    """Write redacted ``results_data`` JSON to *out_path* (creates parent dirs)."""
    payload = redact_paths_in_value(results_data_as_dict(analyzer))
    out_path = out_path.expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=indent, sort_keys=True) + "\n", encoding="utf-8")
    return out_path
