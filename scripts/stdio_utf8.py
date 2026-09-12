"""
UTF-8 stdout helpers for developer CLI scripts.

``sys.stdout`` is typed as ``TextIO`` because it is often monkeypatched. Typeshed
documents narrowing with ``isinstance(..., io.TextIOWrapper)`` before calling
``reconfigure`` — prefer that over ``# pyright: ignore``.

Inputs: none (operates on ``sys.stdout``). Outputs: side effect only; safe no-op
when stdout is not a ``TextIOWrapper`` or when ``reconfigure`` raises
``AttributeError``, ``ValueError``, or ``OSError``.
Requirements: Python 3.9+ standard library.
"""

from __future__ import annotations

import io
import sys


def ensure_stdout_utf8() -> None:
    """Best-effort: set ``sys.stdout`` encoding to UTF-8 when supported.

    No-ops when stdout is not an ``io.TextIOWrapper`` (redirected/patched
    streams) or when ``reconfigure`` is unavailable / refuses the change
    (``AttributeError``, ``ValueError``, or ``OSError``).
    """
    stdout = sys.stdout
    if not isinstance(stdout, io.TextIOWrapper):
        return
    try:
        stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError, OSError):
        return
