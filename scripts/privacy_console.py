"""Standalone-script access to the canonical fail-closed console helper."""

from __future__ import annotations

import sys
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from utils.privacy.console import print_redacted, print_structural_event
from utils.privacy.structural_adapters import (
    print_architecture_baseline_written,
    print_architecture_violation,
    print_license_accepted,
    print_license_obligation,
    print_license_violation,
)

__all__ = [
    "print_architecture_baseline_written",
    "print_architecture_violation",
    "print_license_accepted",
    "print_license_obligation",
    "print_license_violation",
    "print_redacted",
    "print_structural_event",
]
