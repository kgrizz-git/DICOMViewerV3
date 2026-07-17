"""Token and line checks retained alongside the AST sink analysis."""

from __future__ import annotations

import io
import re
import sys
import tokenize
from pathlib import Path

from .models import Violation

ALLOW_PRINT_EXC = "privacy-hook: allow-print_exc"
ALLOW_LINE = "privacy-hook: allow"

_PATIENT_FIELDS: frozenset[str] | None = None
_PRINT_EXC_RE = re.compile(r"traceback\.print_exc\(", re.IGNORECASE)
_LOG_CALL_RE = re.compile(
    r"\b(logger\.(debug|info|warning|error|exception)|print)\s*\(",
    re.IGNORECASE,
)
_PATH_HINT_RE = re.compile(
    r"(?:[A-Za-z]:\\\\|/Users/|/home/|\\\\Users\\\\|Documents\\\\|Downloads\\\\|Desktop\\\\)",
    re.IGNORECASE,
)
_DOC_ABSOLUTE_PATH_RE = re.compile(
    r"(?:[A-Za-z]:\\(?:Users|Documents and Settings)\\|/Users/|/home/|\\\\[A-Za-z0-9][A-Za-z0-9._-]*\\)",
    re.IGNORECASE,
)
_DIALOG_RAW_RE = re.compile(
    r"(?:str\s*\(\s*(?:e|exc|error|exception)\s*\)|"
    r"repr\s*\(\s*(?:e|exc|error|exception)\s*\)|"
    r"\{(?:e|exc|error|exception)(?:\}|!)|traceback\.|format_exc|print_exc)",
    re.IGNORECASE,
)


def _line_allowed(line: str) -> bool:
    return ALLOW_LINE in line.strip() or ALLOW_PRINT_EXC in line.strip()


def _load_patient_fields(repo: Path | None = None) -> frozenset[str]:
    root = repo or Path.cwd()
    src = str((root / "src").resolve())
    if src not in sys.path:
        sys.path.insert(0, src)
    from utils.privacy.classification import SENSITIVE_DICOM_FIELDS

    return frozenset(SENSITIVE_DICOM_FIELDS)


def patient_fields(repo: Path | None = None) -> frozenset[str]:
    """Return the canonical sensitive DICOM field names."""

    global _PATIENT_FIELDS
    if _PATIENT_FIELDS is None:
        _PATIENT_FIELDS = _load_patient_fields(repo)  # pyright: ignore[reportConstantRedefinition]
    return _PATIENT_FIELDS


def reset_patient_fields_cache() -> None:
    """Clear the field-name cache for isolated tests."""

    global _PATIENT_FIELDS
    _PATIENT_FIELDS = None  # pyright: ignore[reportConstantRedefinition]


def _string_and_comment_intervals(
    source: str,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    intervals: list[tuple[tuple[int, int], tuple[int, int]]] = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type in (tokenize.STRING, tokenize.COMMENT):
                intervals.append((token.start, token.end))
    except tokenize.TokenError:
        pass
    return intervals


def _inside(
    position: tuple[int, int],
    interval: tuple[tuple[int, int], tuple[int, int]],
) -> bool:
    start, end = interval
    return start <= position < end


def check_traceback_print_exc(relpath: str, source: str) -> list[Violation]:
    """Flag executable traceback.print_exc calls, excluding strings/comments."""

    intervals = _string_and_comment_intervals(source)
    violations: list[Violation] = []
    for line_number, line in enumerate(source.splitlines(), start=1):
        if _line_allowed(line):
            continue
        if any(
            not any(
                _inside((line_number, match.start()), interval)
                for interval in intervals
            )
            for match in _PRINT_EXC_RE.finditer(line)
        ):
            violations.append(Violation("no-traceback-print-exc", relpath, line_number))
    return violations


def check_patient_fields_in_log_line(
    relpath: str, line: str, lineno: int
) -> list[Violation]:
    """Compatibility check for sensitive field names in output calls."""

    if (
        _line_allowed(line)
        or not _LOG_CALL_RE.search(line)
        or "sanitize_message" in line
        or "sanitize_exception" in line
    ):
        return []
    if any(field.lower() in line.lower() for field in patient_fields()):
        return [Violation("patient-field-in-log", relpath, lineno)]
    return []


def check_path_literal_in_logger_line(
    relpath: str, line: str, lineno: int
) -> list[Violation]:
    """Compatibility check for machine paths embedded in logger calls."""

    if (
        _line_allowed(line)
        or not re.search(
            r"\blogger\.(debug|info|warning|error|exception)\s*\(", line, re.I
        )
        or "sanitize_message" in line
        or "redact_paths=True" in line
        or not _PATH_HINT_RE.search(line)
    ):
        return []
    return [Violation("path-in-log", relpath, lineno)]


def check_absolute_path_in_doc_line(
    relpath: str, line: str, lineno: int
) -> list[Violation]:
    """Flag machine-specific paths without retaining their matched value."""

    if (
        _line_allowed(line)
        or "file://" in line.lower()
        or not _DOC_ABSOLUTE_PATH_RE.search(line)
    ):
        return []
    return [Violation("machine-specific-absolute-path", relpath, lineno)]


def check_dialog_raw_exception(relpath: str, line: str, lineno: int) -> list[Violation]:
    """Compatibility check for raw exceptions in message dialogs."""

    if _line_allowed(line) or "sanitize_" in line or "redact_" in line:
        return []
    if "QMessageBox" not in line and not re.search(
        r"\.(critical|warning|information)\s*\(", line
    ):
        return []
    if _DIALOG_RAW_RE.search(line):
        return [Violation("dialog-raw-exception", relpath, lineno)]
    return []
