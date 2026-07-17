"""Generic user-facing failure text without exception or path details."""

from __future__ import annotations


def generic_error_message(error: BaseException | None = None) -> str:
    """Return actionable generic copy with, at most, a safe error class."""

    if error is None:
        return "The operation could not be completed. No files were changed."
    return (
        "The operation could not be completed. No files were changed. "
        f"Error type: {type(error).__name__}."
    )
