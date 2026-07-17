"""Fail-closed redaction for runtime messages, values, and exceptions."""

from __future__ import annotations

import getpass
import ipaddress
import os
import re
import socket
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from utils.privacy.classification import (
    NORMALIZED_SENSITIVE_NAMES,
    SENSITIVE_DICOM_FIELDS,
)

REDACTED = "[REDACTED]"
REDACTED_PATH = REDACTED
REDACTED_EXCEPTION = "[REDACTED EXCEPTION DETAIL]"

_WINDOWS_PATH = re.compile(
    r"(?<![A-Za-z0-9])(?:[A-Za-z]:\\|\\\\)[^\r\n\t\"'<>|)\],;]+",
    re.IGNORECASE,
)
_POSIX_HOME_PATH = re.compile(
    r"(?<![A-Za-z0-9])/(?:Users|home|root|private/var/folders)/[^\r\n\t\"'<>)\],;]+",
    re.IGNORECASE,
)
_FILE_URI = re.compile(r"\bfile://[^\s\"'<>]+", re.IGNORECASE)
_URL_USERINFO = re.compile(r"\b(?:https?|ftp)://[^\s/@:]+(?::[^\s/@]+)?@[^\s/]+", re.I)
_INTERNAL_HOST = re.compile(
    r"\b[a-z0-9][a-z0-9.-]*\.(?:corp|internal|lan|local)\b", re.I
)
_IP_TOKEN = re.compile(
    r"(?<![0-9A-Fa-f:.])(?:[0-9]{1,3}(?:\.[0-9]{1,3}){3}|[0-9A-Fa-f]{0,4}:[0-9A-Fa-f:.]+)(?![0-9A-Fa-f:.])"
)
_DICOM_UID_VALUE = re.compile(
    r"(?i)(?P<label>\b(?:study|series|sop|frameofreference)?\s*uid\s*[=:]\s*)"
    r"(?P<value>(?:\d+\.){2,}\d+)"
)
_KNOWN_UID_ROOT = re.compile(r"(?<![\d.])(?:2\.25|1\.2\.840)(?:\.\d+){2,}(?![\d.])")
_CONTEXT_VALUE = re.compile(
    r"(?i)(?P<label>\b(?:accession(?:\s+|[_-])?number|mrn|"
    r"patient(?:\s+|[_-])?(?:name|id)|dob|date(?:\s+|[_-])?of(?:\s+|[_-])?birth|"
    r"birth(?:\s+|[_-])?date|"
    r"file(?:\s+|[_-])?(?:name|path)|filename|path|folder|directory|annotation|label|"
    r"username|hostname|ae(?:\s+|[_-])?title)\s*[=:]\s*)"
    r"(?P<value>\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;\]\}]+)"
)
_SAFE_OPERATION = re.compile(r"[a-z][a-z0-9_.-]{0,63}", re.IGNORECASE)
_SAFE_ERROR_CLASS = re.compile(r"[A-Za-z_][A-Za-z0-9_.]{0,127}")
_SAFE_DIAGNOSTIC_KEYS = NORMALIZED_SENSITIVE_NAMES | frozenset(
    {
        "category",
        "count",
        "data",
        "duration_ms",
        "elapsed_ms",
        "error_class",
        "items",
        "nested",
        "operation",
        "status",
        "type",
    }
)


def _local_identity_tokens() -> tuple[str, ...]:
    values = {
        getpass.getuser(),
        os.environ.get("USER", ""),
        os.environ.get("USERNAME", ""),
        socket.gethostname(),
        socket.getfqdn(),
        Path.home().name,
    }
    generic = {"", "root", "runner", "user", "username", "localhost"}
    return tuple(
        sorted(
            {value for value in values if len(value) >= 4 and value.lower() not in generic},
            key=len,
            reverse=True,
        )
    )


def _redact_ip_tokens(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        try:
            address = ipaddress.ip_address(match.group())
        except ValueError:
            return match.group()
        if address.is_loopback:
            return match.group()
        return REDACTED

    return _IP_TOKEN.sub(replace, text)


def _redact_named_fields(text: str) -> str:
    redacted = text
    for field in sorted(SENSITIVE_DICOM_FIELDS, key=len, reverse=True):
        pattern = re.compile(
            rf"(?i)(?P<label>\b{re.escape(field)}\s*[=:]\s*)"
            rf"(?P<value>\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;\]\}}]+)"
        )
        redacted = pattern.sub(lambda m: f"{m.group('label')}{REDACTED}", redacted)
    return redacted


def redact_text(message: Any, *, redact_paths: bool = True) -> str:
    """Return a redacted string safe for a runtime output sink.

    ``redact_paths`` remains for source compatibility, but absolute user paths
    are always removed.  A caller cannot opt out of protecting filenames by
    passing ``False``.
    """

    _ = redact_paths
    if message is None:
        return ""
    try:
        text = str(message)
    except Exception:
        return REDACTED
    if not text:
        return text

    text = _FILE_URI.sub(REDACTED_PATH, text)
    text = _WINDOWS_PATH.sub(REDACTED_PATH, text)
    text = _POSIX_HOME_PATH.sub(REDACTED_PATH, text)
    home = str(Path.home())
    if home and home != os.path.sep:
        text = text.replace(home, REDACTED_PATH)
    text = _URL_USERINFO.sub(REDACTED, text)
    text = _INTERNAL_HOST.sub(REDACTED, text)
    text = _redact_ip_tokens(text)
    text = _DICOM_UID_VALUE.sub(lambda m: f"{m.group('label')}{REDACTED}", text)
    text = _KNOWN_UID_ROOT.sub(REDACTED, text)
    text = _redact_named_fields(text)
    text = _CONTEXT_VALUE.sub(lambda m: f"{m.group('label')}{REDACTED}", text)

    for identity in _local_identity_tokens():
        text = re.sub(
            rf"(?<![A-Za-z0-9_.-]){re.escape(identity)}(?![A-Za-z0-9_.-])",
            REDACTED,
            text,
            flags=re.IGNORECASE,
        )
    return text


def _normalized_key(key: Any) -> str:
    return str(key).strip().lower().replace("-", "_").replace(" ", "_")


def redact_value(value: Any, *, key: Any | None = None) -> Any:
    """Recursively redact a logging/report value without retaining identifiers."""

    if key is not None and _normalized_key(key) in NORMALIZED_SENSITIVE_NAMES:
        return REDACTED
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return {str(k): redact_value(v, key=k) for k, v in value.items()}
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [redact_value(item) for item in value]
    if isinstance(value, (bytes, bytearray)):
        return REDACTED
    return redact_text(value)


def _diagnostic_key(key: Any, index: int) -> str:
    """Return an allow-listed structural key without stringifying arbitrary data."""

    try:
        normalized = _normalized_key(key)
    except Exception:
        return f"field_{index}"
    if normalized in _SAFE_DIAGNOSTIC_KEYS:
        return normalized
    return f"field_{index}"


def redact_diagnostic_value(value: Any, *, key: Any | None = None) -> Any:
    """Recursively reduce diagnostic values to safe structure and typed metrics.

    Arbitrary strings and mapping keys are data, not trustworthy labels. They are
    removed unless the value is a validated operation identifier or exception
    class. This is deliberately stricter than :func:`redact_text`, whose pattern
    matching is intended for already-authored human-facing messages.
    """

    normalized_key = _normalized_key(key) if key is not None else ""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if normalized_key == "operation" and _SAFE_OPERATION.fullmatch(value):
            return value
        if normalized_key == "error_class" and _SAFE_ERROR_CLASS.fullmatch(value):
            return value
        return REDACTED
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for index, (item_key, item_value) in enumerate(value.items()):
            safe_key = _diagnostic_key(item_key, index)
            while safe_key in result:
                safe_key = f"field_{index}_{len(result)}"
            result[safe_key] = redact_diagnostic_value(item_value, key=safe_key)
        return result
    if isinstance(value, tuple):
        return tuple(redact_diagnostic_value(item) for item in value)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [redact_diagnostic_value(item) for item in value]
    return REDACTED


def safe_event_fields(
    operation: str,
    *,
    count: int | None = None,
    error: BaseException | type[BaseException] | None = None,
) -> dict[str, str | int]:
    """Build a deliberately small structured event without sensitive values."""

    if not _SAFE_OPERATION.fullmatch(operation):
        raise ValueError("operation must be a stable non-sensitive identifier")
    fields: dict[str, str | int] = {"operation": operation}
    if count is not None:
        if isinstance(count, bool) or count < 0:
            raise ValueError("count must be a non-negative integer")
        fields["count"] = count
    if error is not None:
        error_type = error if isinstance(error, type) else type(error)
        fields["error_class"] = error_type.__name__
    return fields


def redact_exception(value: BaseException | str | None) -> str:
    """Return only safe exception structure and class information."""

    if value is None:
        return ""
    if isinstance(value, BaseException):
        return f"{type(value).__name__}: {REDACTED_EXCEPTION}"

    lines: list[str] = []
    for raw_line in str(value).splitlines():
        stripped = raw_line.strip()
        if not stripped:
            lines.append("")
        elif stripped.startswith("Traceback"):
            lines.append("Traceback (redacted):")
        elif stripped.startswith("File "):
            line_number = re.search(r"\bline\s+(\d+)", stripped)
            function = re.search(r"\bin\s+([A-Za-z_][A-Za-z0-9_]*)", stripped)
            detail = f'  File "{REDACTED_PATH}"'
            if line_number:
                detail += f", line {line_number.group(1)}"
            if function:
                detail += f", in {function.group(1)}"
            lines.append(detail)
        else:
            exception_class = re.match(
                r"(?:[A-Za-z_][\w.]*\.)?([A-Za-z_][\w]*(?:Error|Exception|Warning))\s*:",
                stripped,
            )
            if exception_class:
                lines.append(f"{exception_class.group(1)}: {REDACTED_EXCEPTION}")
            elif raw_line[:1].isspace():
                lines.append("    [REDACTED TRACEBACK CONTEXT]")
            else:
                lines.append(redact_text(raw_line))
    return "\n".join(lines)
