"""Fail-closed console output for dynamic diagnostic values."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from typing import Any, TextIO

from utils.privacy.redaction import REDACTED, redact_diagnostic_value, redact_exception
from utils.privacy.structural_events import (
    StructuralEvent,
    render_structural_event,
    structural_event,
)


def _render_console_value(value: Any) -> str:
    """Render only typed metrics, safe structure, or an explicit redaction marker."""

    if isinstance(value, BaseException):
        return redact_exception(value)
    if isinstance(value, StructuralEvent):
        return render_structural_event(value)
    reduced = redact_diagnostic_value(value)
    if isinstance(reduced, (Mapping, Sequence)) and not isinstance(reduced, str):
        return json.dumps(reduced, sort_keys=True)
    if reduced is None:
        return ""
    if isinstance(reduced, (bool, int, float)):
        return str(reduced)
    return REDACTED


def print_redacted(
    *values: Any,
    sep: str = " ",
    end: str = "\n",
    file: TextIO | None = None,
    flush: bool = False,
) -> None:
    """Write dynamic diagnostics without allowing arbitrary strings to escape."""

    stream = file or sys.stdout
    rendered = sep.join(_render_console_value(value) for value in values)
    stream.write(rendered + end)
    if flush:
        stream.flush()


def print_structural_event(
    operation: str,
    *,
    category: str | None = None,
    error: BaseException | type[BaseException] | None = None,
    identifiers: Mapping[str, Any] | None = None,
    metrics: Mapping[str, Any] | None = None,
    sep: str = " ",
    end: str = "\n",
    file: TextIO | None = None,
    flush: bool = False,
) -> None:
    """Write a validated structural event with print-compatible controls."""

    stream = file or sys.stdout
    event = structural_event(
        operation,
        category=category,
        error=error,
        identifiers=identifiers,
        metrics=metrics,
    )
    stream.write(render_structural_event(event, sep=sep) + end)
    if flush:
        stream.flush()
