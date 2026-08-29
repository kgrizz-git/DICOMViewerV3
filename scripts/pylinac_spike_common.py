"""
Shared helpers for pylinac ACR spike scripts (Phase 0 ``results_data`` fixture dumps).

Used by ``spike_pylinac_acrct.py`` and ``spike_pylinac_acrmri.py`` to call
``analyzer.results_data(as_dict=True)``, drop site/PHI keys, redact filesystem
paths, and write JSON for ``tests/fixtures/qa/``. Maintainer-only: requires
local gitignored phantom data.

Inputs:
    A post-``analyze()`` pylinac analyzer, or an already-built results dict.

Outputs:
    A dump tree with absolute paths replaced by ``<redacted-path>`` and
    institution / station / patient / UID-like DICOM keywords omitted.

Requirements:
    Never write dumps inside the source checkout (callers use
    ``assert_safe_internal_path``). Never log folder or dump destination paths.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

_SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from utils.privacy.classification import SENSITIVE_DICOM_FIELDS

# Extra site/device keywords that may appear even if not in the DICOM registry.
_EXTRA_DUMP_DROP_KEYS = frozenset(
    {
        "InstitutionalDepartmentName",
        "InstitutionCodeSequence",
        "PerformedStationName",
        "ManufacturerModelName",
    }
)

_DUMP_DROP_KEYS_LOWER = frozenset(
    key.lower() for key in (SENSITIVE_DICOM_FIELDS | _EXTRA_DUMP_DROP_KEYS)
)

# Absolute Unix paths and Windows drive paths (conservative redaction for fixtures).
_UNIX_ABS = re.compile(r"(?<![\w./-])(/[\w./-]+)")
_WIN_ABS = re.compile(r"(?<![\w:])[A-Za-z]:[\\/][\w. \\/-]+")


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


def _is_dump_drop_key(key: object) -> bool:
    """True when *key* is a DICOM/site identifier that must not appear in dumps."""
    return str(key).strip().lower() in _DUMP_DROP_KEYS_LOWER


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


def drop_sensitive_dump_keys(value: Any) -> Any:
    """Omit institution, station, patient, and UID-like keys from a dump tree."""
    if isinstance(value, dict):
        return {
            str(key): drop_sensitive_dump_keys(child)
            for key, child in value.items()
            if not _is_dump_drop_key(key)
        }
    if isinstance(value, (list, tuple)):
        return [drop_sensitive_dump_keys(item) for item in value]
    return value


def redact_results_dump(value: Any) -> Any:
    """Drop site/PHI keys, then redact any remaining absolute paths."""
    return redact_paths_in_value(drop_sensitive_dump_keys(value))


def analyze_folder_with_extent_retry(
    analyzer_cls: type,
    folder: Path,
    *,
    check_uid: bool = False,
    analyze_kwargs: dict[str, Any] | None = None,
    tolerances_mm: tuple[float, ...] = (0.0, 1.0, 2.0),
) -> Any:
    """
    Construct a viewer ACR analyzer and ``analyze()`` with scan-extent retries.

    Pylinac ACR classes take the folder path in ``__init__`` (there is no
    ``from_folder``). Tracked T1 axials need the same ~1 mm extent retry the
    viewer offers; strict z-extent often fails first.
    """
    kwargs = dict(analyze_kwargs or {})
    last_error: BaseException | None = None
    for tol in tolerances_mm:
        analyzer = analyzer_cls(str(folder), check_uid=check_uid)
        analyzer._scan_extent_tolerance_mm = float(tol)
        try:
            analyzer.analyze(**kwargs)
        except ValueError as exc:
            last_error = exc
            continue
        return analyzer
    if last_error is not None:
        raise last_error
    raise RuntimeError("analyze failed")


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
    payload = redact_results_dump(results_data_as_dict(analyzer))
    out_path = out_path.expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=indent, sort_keys=True) + "\n", encoding="utf-8")
    return out_path
