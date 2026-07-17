"""Finding model and deliberately redacted output formatting."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePosixPath

CRITICAL_RULES = frozenset(
    {
        "dialog-raw-exception",
        "file-read",
        "git-read",
        "logging-exc-info",
        "logging-exception",
        "no-traceback-print-exc",
        "performance-event-fields",
        "performance-event-label",
        "structural-adapter-scope",
        "structural-event-arguments",
        "structural-event-category",
        "structural-event-direct-construction",
        "structural-event-error",
        "structural-event-identifiers",
        "structural-event-direct-render",
        "structural-event-low-level-allocation",
        "structural-event-metrics",
        "structural-event-operation",
        "structural-event-private-mutation",
        "structural-event-private-sealing",
        "structural-schema",
        "syntax",
        "traceback-output",
        "unsafe-logger-argument",
        "unsafe-stream-write",
    }
)


@dataclass(frozen=True, slots=True)
class Violation:
    """One source location and privacy rule category.

    Findings intentionally do not retain source excerpts, matched values, or
    exception messages. This makes accidental disclosure by later formatters
    structurally impossible.
    """

    rule: str
    path: str
    line: int

    def __post_init__(self) -> None:
        normalized = PurePosixPath(self.path.replace("\\", "/"))
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ValueError("violation paths must be repository-relative")


def format_violations(violations: Iterable[Violation]) -> str:
    """Render only repository-relative path, line, and rule category."""

    return "\n".join(
        f"{violation.path}:{violation.line}: [{violation.rule}]"
        for violation in violations
    )


def critical_violations(violations: Iterable[Violation]) -> list[Violation]:
    """Return the blocking subset used by the full-tree critical gate."""

    return [violation for violation in violations if violation.rule in CRITICAL_RULES]
