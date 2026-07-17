"""Narrow typed adapters for reviewed dynamic license and architecture fields."""

from __future__ import annotations

import sys
from typing import Any, Literal, TextIO

from utils.privacy.structural_events import (
    StructuralEvent,
    _architecture_event,  # pyright: ignore[reportPrivateUsage]
    _license_event,  # pyright: ignore[reportPrivateUsage]
    render_structural_event,
)

LicenseExceptionCategory = Literal["FORBIDDEN", "UNKNOWN"]
ArchitectureCategory = Literal[
    "core-gui", "domain-main", "gui-main", "syntax", "utils-domain"
]


def _write(event: StructuralEvent, *, file: TextIO | None = None) -> None:
    stream = file or sys.stdout
    stream.write(render_structural_event(event) + "\n")


def print_license_obligation(
    *, package: Any, version: Any, license_name: Any, source: Any
) -> None:
    """Print one obligation row from installed-distribution metadata."""

    _write(
        _license_event(
            "license.obligation",
            category="OBLIGATION",
            package=package,
            version=version,
            license_name=license_name,
            source=source,
        )
    )


def print_license_accepted(
    category: LicenseExceptionCategory,
    *,
    package: Any,
    version: Any,
    license_name: Any,
    source: Any,
) -> None:
    """Print one policy-accepted forbidden/unknown dependency row."""

    _write(
        _license_event(
            "license.accepted",
            category=category,
            package=package,
            version=version,
            license_name=license_name,
            source=source,
        )
    )


def print_license_violation(
    category: LicenseExceptionCategory,
    *,
    package: Any,
    version: Any,
    license_name: Any,
    source: Any,
) -> None:
    """Print one non-accepted forbidden/unknown dependency row."""

    _write(
        _license_event(
            "license.violation",
            category=category,
            package=package,
            version=version,
            license_name=license_name,
            source=source,
        )
    )


def print_architecture_violation(
    category: ArchitectureCategory,
    *,
    module: Any,
    repository_path: Any,
    line: Any,
    file: TextIO | None = None,
) -> None:
    """Print one repository-source architecture violation."""

    _write(
        _architecture_event(
            "architecture.violation",
            category=category,
            module=module,
            repository_path=repository_path,
            line=line,
        ),
        file=file,
    )


def print_architecture_baseline_written(*, count: Any) -> None:
    """Print the typed count for a refreshed architecture baseline."""

    _write(
        _architecture_event(
            "architecture.baseline_written", count=count
        )
    )


__all__ = [
    "ArchitectureCategory",
    "LicenseExceptionCategory",
    "print_architecture_baseline_written",
    "print_architecture_violation",
    "print_license_accepted",
    "print_license_obligation",
    "print_license_violation",
]
