"""Fail-closed stdout/stderr boundary for application-process diagnostics."""

from __future__ import annotations

import sys
from typing import Any, TextIO

from utils.privacy.redaction import redact_text


class PrivacyTextStream:
    """Delegate a text stream while redacting every emitted string."""

    def __init__(self, wrapped: TextIO) -> None:
        self._wrapped = wrapped

    def write(self, text: str) -> int:
        return self._wrapped.write(redact_text(text))

    def flush(self) -> None:
        self._wrapped.flush()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)


def install_privacy_streams() -> tuple[PrivacyTextStream, PrivacyTextStream]:
    """Install idempotent redacting boundaries and return the active streams."""

    if not isinstance(sys.stdout, PrivacyTextStream):
        sys.stdout = PrivacyTextStream(sys.stdout)  # type: ignore[assignment]
    if not isinstance(sys.stderr, PrivacyTextStream):
        sys.stderr = PrivacyTextStream(sys.stderr)  # type: ignore[assignment]
    return sys.stdout, sys.stderr
