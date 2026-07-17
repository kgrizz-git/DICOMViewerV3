"""Direct-script bootstrap for the canonical privacy console helper."""

from __future__ import annotations

import sys
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from utils.privacy.console import print_redacted, print_structural_event

__all__ = ["print_redacted", "print_structural_event"]
